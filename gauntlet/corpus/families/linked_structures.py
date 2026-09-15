"""Linked structures: the chain, the ring, and the vault built out of both.

A linked list is the first data structure in a timed practical that is not a Python
builtin. There is no `len`, no indexing, no slicing — there is a node, and the
node knows exactly one thing: what comes after it. Everything in this family is
a consequence of that.

The corpus had no coverage of it at all, which meant a player could clear ten
chapters and still freeze on "reverse a linked list".

THE RAMP. Every technique here is introduced three times before it is ever asked
for cold: as a GUIDED scaffold with one or two runes struck out, then as a
TUTORIAL write-up of the same shape, then as an EASY variation, and only then at
MEDIUM or above. A player who meets `reverse_between` has already written the
three-pointer rewiring twice with their own hands.

THE NODE IS REAL. The player writes against an actual `ListNode`, not a Python
list pretending to be one, because "just use a list" is the exact reflex an
examiner is testing for the absence of. Tests still travel as plain value
lists; the sandbox harness turns them into a chain on the way in and back into
values on the way out (`arg_adapters=["linked"]`, `result_adapter="linked"`),
which mirrors what `_tree.py` already does for `TreeNode`.
"""
from __future__ import annotations

from ._base import code_problem, design_problem
from .scaffolds import rune

# ---------------------------------------------------------------------------
# Build-time mirrors of the sandbox adapters
# ---------------------------------------------------------------------------
#
# These exist so the *reference* implementation can be written against real
# nodes too. If the build-time chain and the in-sandbox chain ever disagreed,
# every expected value in this file would be quietly wrong, so the two are kept
# deliberately identical in shape to `gauntlet/_harness.py`.


class ListNode:
    __slots__ = ("val", "next")

    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class DListNode:
    __slots__ = ("val", "prev", "next")

    def __init__(self, val=0, prev=None, next=None):
        self.val = val
        self.prev = prev
        self.next = next


PREAMBLE = """
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
"""

DLL_PREAMBLE = """
class DListNode:
    def __init__(self, val=0, prev=None, next=None):
        self.val = val
        self.prev = prev
        self.next = next
"""

LIST_SHAPE = ("`head` is a `ListNode` with `.val` and `.next`; the last node's `.next` "
              "is `None`, and an empty list is `head is None`.")

DLL_SHAPE = ("`DListNode` is already defined for you, with `.val`, `.prev` and `.next`. "
             "You are given the values, so you build the chain yourself.")

LIST_HINT = "head is a ListNode with .val and .next; the last node's .next is None"
DLL_HINT = "DListNode has .val, .prev and .next; build the chain from `values` yourself"

VIZ_CHAIN = {"type": "array_scan", "caption": "One node knows one thing: what follows."}
VIZ_POINTERS = {"type": "two_pointer", "caption": "Two walkers, different speeds."}
VIZ_REC = {"type": "recursion", "caption": "Trust the smaller chain."}
VIZ_MAP = {"type": "hash_map", "caption": "Identity remembered, order kept elsewhere."}

Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 3.0, "SECURITY_ENGINEERING": 1.5}


def to_linked(values):
    if not values:
        return None
    head = ListNode(values[0])
    cur = head
    for value in values[1:]:
        cur.next = ListNode(value)
        cur = cur.next
    return head


def to_cycle(values, pos=-1):
    """Build a chain whose tail links back to index `pos`. `pos < 0` means none."""
    if not values:
        return None
    nodes = [ListNode(v) for v in values]
    for node, nxt in zip(nodes, nodes[1:]):
        node.next = nxt
    if 0 <= pos < len(nodes):
        nodes[-1].next = nodes[pos]
    return nodes[0]


def from_linked(node):
    """Read a chain back into values. The seen-set is load-bearing: a reference
    that accidentally produced a ring would otherwise hang the build."""
    out, seen = [], set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        out.append(node.val)
        node = node.next
    return out


def linked_ref(fn, *, heads=1, returns_list=False, cycle=False):
    """Wrap a ListNode-taking reference so it accepts plain value lists.

    `heads` is how many leading arguments are chains. `cycle` means the first
    argument is a `[values, pos]` pair, matching the `linked_cycle` adapter.
    """
    def wrapper(*args):
        converted = list(args)
        if cycle:
            spec = list(converted[0])
            converted[0] = to_cycle(spec[0], spec[1] if len(spec) > 1 else -1)
        else:
            for i in range(heads):
                converted[i] = to_linked(converted[i])
        result = fn(*converted)
        return from_linked(result) if returns_list else result
    return wrapper


# ---------------------------------------------------------------------------
# References. Each is an independent implementation of the problem, written to
# disagree with the canonical solution in method wherever it honestly can. The
# validator only ships a problem when the two agree on every single test.
# ---------------------------------------------------------------------------

def _values(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out


def _ref_list_values(head):
    return _values(head)


def _ref_length(head):
    return len(_values(head))


def _ref_sum(head):
    return sum(_values(head))


def _ref_build(values):
    return list(values)


def _ref_value_at(head, index):
    vals = _values(head)
    if index < 0 or index >= len(vals):
        return None
    return vals[index]


def _ref_reverse(head):
    return _values(head)[::-1]


def _ref_reverse_between(head, left, right):
    vals = _values(head)
    lo, hi = left - 1, right
    vals[lo:hi] = vals[lo:hi][::-1]
    return vals


def _ref_swap_pairs(head):
    vals = _values(head)
    for i in range(0, len(vals) - 1, 2):
        vals[i], vals[i + 1] = vals[i + 1], vals[i]
    return vals


def _ref_middle(head):
    vals = _values(head)
    return vals[len(vals) // 2] if vals else None


def _ref_nth_from_end(head, n):
    vals = _values(head)
    if n < 1 or n > len(vals):
        return None
    return vals[len(vals) - n]


def _ref_has_cycle(head):
    seen = set()
    while head is not None:
        if id(head) in seen:
            return True
        seen.add(id(head))
        head = head.next
    return False


def _ref_cycle_length(head):
    seen = {}
    step = 0
    while head is not None:
        if id(head) in seen:
            return step - seen[id(head)]
        seen[id(head)] = step
        step += 1
        head = head.next
    return 0


def _ref_cycle_entry(head):
    seen = set()
    while head is not None:
        if id(head) in seen:
            return head.val
        seen.add(id(head))
        head = head.next
    return None


def _ref_remove_nth_from_end(head, n):
    vals = _values(head)
    if 1 <= n <= len(vals):
        del vals[len(vals) - n]
    return vals


def _ref_merge_sorted(a, b):
    return sorted(_values(a) + _values(b))


def _ref_alternate(a, b):
    left, right = _values(a), _values(b)
    out = []
    for i in range(max(len(left), len(right))):
        if i < len(left):
            out.append(left[i])
        if i < len(right):
            out.append(right[i])
    return out


def _ref_merge_three(a, b, c):
    return sorted(_values(a) + _values(b) + _values(c))


def _ref_remove_value(head, target):
    return [v for v in _values(head) if v != target]


def _ref_dedupe_sorted(head):
    out = []
    for value in _values(head):
        if not out or out[-1] != value:
            out.append(value)
    return out


def _ref_delete_all_duplicates(head):
    vals = _values(head)
    return [v for v in vals if vals.count(v) == 1]


def _ref_dedupe_unsorted(head):
    out = []
    for value in _values(head):
        if value not in out:
            out.append(value)
    return out


def _ref_partition(head, x):
    vals = _values(head)
    return [v for v in vals if v < x] + [v for v in vals if v >= x]


def _ref_digits_to_number(head):
    return int("".join(str(d) for d in reversed(_values(head))) or "0")


def _ref_number_to_digits(number):
    return [int(ch) for ch in str(number)][::-1]


def _ref_add_one(head):
    return _ref_number_to_digits(_ref_digits_to_number(head) + 1)


def _ref_add_two(a, b):
    return _ref_number_to_digits(_ref_digits_to_number(a) + _ref_digits_to_number(b))


def _ref_is_palindrome(head):
    vals = _values(head)
    for i in range(len(vals) // 2):
        if vals[i] != vals[-1 - i]:
            return False
    return True


def _ref_second_half(head):
    vals = _values(head)
    return vals[len(vals) // 2:]


def _ref_reorder(head):
    vals = _values(head)
    out = []
    lo, hi = 0, len(vals) - 1
    while lo < hi:
        out.append(vals[lo])
        out.append(vals[hi])
        lo += 1
        hi -= 1
    if lo == hi:
        out.append(vals[lo])
    return out


def _ref_shared_tail(a, b):
    """Longest common suffix, computed from the tails inward. Nothing in here
    resembles the length-alignment walk the canonical solution uses."""
    left, right = _values(a), _values(b)
    shared = 0
    while shared < len(left) and shared < len(right) \
            and left[-1 - shared] == right[-1 - shared]:
        shared += 1
    return left[-shared] if shared else None


def _ref_read_backward(values):
    return list(values)[::-1]


def _ref_dll_remove(values, target):
    out = list(values)
    if target in out:
        out.remove(target)
    return [out, out[::-1]]


def _lru_trace(capacity, keys):
    """One simulation, three questions asked of it.

    Deliberately timestamp-based rather than list-order-based, because the
    canonical solutions maintain an explicit order list. Two methods, same
    answers, or the problem does not ship.
    """
    last_used, evicted, hits = {}, [], 0
    for step, key in enumerate(keys):
        if key in last_used:
            hits += 1
        last_used[key] = step
        if len(last_used) > capacity:
            victim = min(last_used, key=last_used.get)
            del last_used[victim]
            evicted.append(victim)
    order = sorted(last_used, key=last_used.get)
    return order, evicted, hits


def _ref_lru_order(capacity, keys):
    return _lru_trace(capacity, keys)[0]


def _ref_lru_evictions(capacity, keys):
    return _lru_trace(capacity, keys)[1]


def _ref_lru_hits(capacity, keys):
    return _lru_trace(capacity, keys)[2]


class RefDeque:
    """A list stands in for the doubly linked list the player must build. The
    behaviour is the contract; the structure is the lesson."""

    def __init__(self):
        self.items = []

    def push_front(self, value):
        self.items.insert(0, value)
        return None

    def push_back(self, value):
        self.items.append(value)
        return None

    def pop_front(self):
        return self.items.pop(0) if self.items else None

    def pop_back(self):
        return self.items.pop() if self.items else None

    def to_list(self):
        return list(self.items)

    def size(self):
        return len(self.items)


class RefLRUCache:
    """OrderedDict, deliberately — the player is asked for dict + doubly linked
    list, so the reference must reach the same answers by a different road."""

    def __init__(self, capacity=2):
        from collections import OrderedDict
        self.capacity = capacity
        self.store = OrderedDict()

    def get(self, key):
        if key not in self.store:
            return -1
        self.store.move_to_end(key)
        return self.store[key]

    def put(self, key, value):
        if key in self.store:
            self.store.move_to_end(key)
        self.store[key] = value
        if len(self.store) > self.capacity:
            self.store.popitem(last=False)
        return None

    def keys(self):
        """Most recently used first — the order the player's linked list holds."""
        return list(self.store)[::-1]


# ---------------------------------------------------------------------------
# The family
# ---------------------------------------------------------------------------

def build() -> list:
    P: list = []

    chain = dict(preamble=PREAMBLE, arg_adapters=["linked"], starter_hint=LIST_HINT)
    pair = dict(preamble=PREAMBLE, arg_adapters=["linked", "linked"],
                starter_hint=LIST_HINT)
    ring = dict(preamble=PREAMBLE, arg_adapters=["linked_cycle"],
                starter_hint=LIST_HINT)

    # == THE CHAIN ITSELF ====================================================

    P.append(rune(
        id="ll-walk-guided", title="The First Link", realm="fields_of_syntax",
        difficulty="GUIDED", family="linked_list", pattern="SIMULATION",
        scaffold_for="LINKED LIST: walking the chain", **chain,
        statement="""
            Return every value in the chain, in order, as an ordinary Python list.

            A linked list has no indexes and no length. It has a first node, and
            every node holds the one after it:

            ```python
            class ListNode:
                def __init__(self, val=0, next=None):
                    self.val = val
                    self.next = next
            ```

            So walking it is a loop with a cursor. Two runes are missing: the
            condition that says the chain is not finished, and the step that moves
            the cursor along. Get the second one wrong and the loop runs forever.
        """,
        fn_name="list_values", params="head", reference=linked_ref(_ref_list_values),
        canonical="""
            def list_values(head):
                out = []
                node = head
                while node is not None:
                    out.append(node.val)
                    node = node.next
                return out
        """,
        blanks=[("node is not None", "there is still a node under the cursor"),
                ("node = node.next", "move the cursor one link along")],
        visible=[("three", [[1, 2, 3]]), ("one", [[7]])],
        hidden=[("negatives", [[-1, 0, 5]]), ("repeats", [[4, 4, 4, 4]])],
        edges=[("empty", [[]])],
        constraints=["0 <= number of nodes <= 1000"],
        failures=["`while node.next`, which drops the last value",
                  "Forgetting to advance the cursor, which hangs the loop"],
        nudge="`head` is a node, not a list. The only question you can ask a node "
              "is: what comes after you?",
        visual="A cursor starts on the first node and hops forward until it falls "
               "off the end into None.",
        pseudocode="""
            node = head
            while there is a node:
                record node.val
                node = node.next
        """,
        time_complexity="O(n)", space_complexity="O(n)",
        tags=["core", "linked-list"],
    ))

    P.append(rune(
        id="ll-length-guided", title="Counting the Links", realm="fields_of_syntax",
        difficulty="GUIDED", family="linked_list", pattern="SIMULATION",
        scaffold_for="LINKED LIST: walking the chain", **chain,
        statement="""
            Return how many nodes are in the chain. `len()` does not work on a
            linked list — there is nothing to ask but the nodes themselves.

            """ + LIST_SHAPE + """
        """,
        fn_name="list_length", params="head", reference=linked_ref(_ref_length),
        canonical="""
            def list_length(head):
                count = 0
                node = head
                while node is not None:
                    count += 1
                    node = node.next
                return count
        """,
        blanks=[("count += 1", "one more node has been walked past"),
                ("node = node.next", "move the cursor, or this loop never ends")],
        visible=[("four", [[1, 2, 3, 4]]), ("one", [[9]])],
        hidden=[("zeros", [[0, 0]]), ("long", [list(range(20))])],
        edges=[("empty", [[]])],
        failures=["Counting links instead of nodes and returning n - 1"],
        nudge="Count as you go. There is no second pass available to you.",
        visual="One counter, one cursor, one pass.",
        pseudocode="""
            count = 0
            walk the chain, adding one per node
            return count
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-sum", title="The Weight of the Chain", realm="fields_of_syntax",
        difficulty="TUTORIAL", family="linked_list", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, **chain,
        statement="""
            Return the sum of every value in the chain. An empty chain sums to `0`.

            """ + LIST_SHAPE + """

            This is the walk you have already written twice, with an accumulator
            instead of a list. Write the whole function this time.
        """,
        fn_name="sum_values", params="head", reference=linked_ref(_ref_sum),
        canonical="""
            def sum_values(head):
                total = 0
                node = head
                while node is not None:
                    total += node.val
                    node = node.next
                return total
        """,
        visible=[("three", [[1, 2, 3]]), ("one", [[10]])],
        hidden=[("negatives", [[5, -5, 5]]), ("zeros", [[0, 0, 0]]),
                ("longer", [list(range(1, 11))])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Starting the total at the first node's value and then visiting "
                  "that node again"],
        nudge="Accumulator outside the loop, cursor inside it.",
        visual="Same walk as before. Only what you do at each node changes.",
        pseudocode="""
            total = 0
            walk the chain: total += node.val
            return total
        """,
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-build", title="Forging a Chain", realm="fields_of_syntax",
        difficulty="TUTORIAL", family="linked_list", pattern="SIMULATION",
        preamble=PREAMBLE, arg_adapters=[], result_adapter="linked",
        starter_hint="build ListNode objects and return the FIRST one",
        viz=VIZ_CHAIN, profile_weight=Q,
        statement="""
            You are given a plain Python list of `values`. Build a linked chain from
            it and return the head node. An empty list makes an empty chain: return
            `None`.

            `ListNode(val, next)` is already defined, and its second argument is the
            node that follows. Building from the back is therefore one line per
            node — but building from the front works too, if you keep hold of the
            tail.

            Your answer is read back out as a list of values.
        """,
        fn_name="build_list", params="values", reference=_ref_build,
        canonical="""
            def build_list(values):
                head = None
                for value in reversed(values):
                    head = ListNode(value, head)     # the chain grows backwards
                return head
        """,
        visible=[("three", [[1, 2, 3]]), ("one", [[42]])],
        hidden=[("negatives", [[-1, -2]]), ("repeats", [[7, 7, 7]]),
                ("longer", [list(range(8))])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Returning the last node instead of the first",
                  "Building forwards without keeping a tail cursor, so every node "
                  "overwrites the one before it"],
        nudge="Every node you create needs to know what follows it. Going right to "
              "left, you always already know.",
        visual="Start from None and hang each value in front of what you have.",
        pseudocode="""
            head = None
            for value from last to first:
                head = a new node holding value, pointing at head
        """,
        alternates=[{"name": "forward build with a dummy head and a tail cursor",
                     "note": "What you will use for every 'return a new list' problem "
                             "from here on.",
                     "complexity": "O(n)"}],
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-value-at", title="The Node with No Address", realm="fields_of_syntax",
        difficulty="EASY", family="linked_list", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, **chain,
        statement="""
            Return the value of the node at position `index`, counting from `0`.
            Return `None` if `index` is negative or past the end.

            """ + LIST_SHAPE + """

            `head[3]` does not exist. Getting to position 3 costs three steps, and
            that cost is the whole reason arrays and linked lists are different
            structures.
        """,
        fn_name="value_at", params="head, index", reference=linked_ref(_ref_value_at),
        canonical="""
            def value_at(head, index):
                if index < 0:
                    return None
                node = head
                steps = 0
                while node is not None:
                    if steps == index:
                        return node.val
                    node = node.next
                    steps += 1
                return None
        """,
        visible=[("middle", [[10, 20, 30], 1]), ("first", [[10, 20, 30], 0])],
        hidden=[("last", [[10, 20, 30], 2]), ("past the end", [[10, 20, 30], 3]),
                ("negative", [[1, 2, 3], -1]), ("single", [[5], 0])],
        edges=[("empty", [[], 0]), ("empty negative", [[], -2])],
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(log n)", "O(n)", "O(n log n)"],
        failures=["Walking off the end and raising AttributeError on None.val",
                  "Off by one: stopping after `index` steps instead of at step `index`",
                  "Forgetting the negative case"],
        nudge="Count your steps as you walk, and stop the instant the chain does.",
        visual="Position is not an address here. It is a number of hops.",
        pseudocode="""
            reject negative index
            walk with a step counter
            when steps == index: return this node's value
            ran out of chain -> None
        """,
        prerequisites=["ll-sum"], tags=["core", "linked-list"],
    ))

    # == REVERSAL ============================================================

    P.append(rune(
        id="ll-reverse-guided", title="The Rune of the Turned Chain",
        realm="twin_pointer_pass", difficulty="GUIDED", family="linked_reverse",
        pattern="TWO_POINTER", scaffold_for="LINKED LIST: pointer rewiring",
        result_adapter="linked", **chain,
        statement="""
            Reverse the chain and return the new head.

            """ + LIST_SHAPE + """

            You cannot reverse a chain by swapping values around, because you cannot
            walk backwards to put them anywhere. You reverse it by turning each
            `.next` around as you pass it.

            Three cursors do this: `prev` (the part already turned), `node` (the one
            being turned) and a saved copy of what came next. Two runes are missing,
            and they are the two that people get wrong: saving the rest of the chain
            before you destroy the link to it, and actually turning the link.
        """,
        fn_name="reverse_list", params="head", reference=linked_ref(_ref_reverse),
        canonical="""
            def reverse_list(head):
                prev = None
                node = head
                while node is not None:
                    following = node.next
                    node.next = prev
                    prev = node
                    node = following
                return prev
        """,
        blanks=[("node.next", "the rest of the chain, saved BEFORE the link is overwritten"),
                ("node.next = prev", "turn this node's arrow around")],
        visible=[("three", [[1, 2, 3]]), ("two", [[1, 2]])],
        hidden=[("five", [[1, 2, 3, 4, 5]]), ("repeats", [[7, 7, 8]]),
                ("negatives", [[-1, -2, -3]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        failures=["Overwriting `node.next` before saving it, which loses the tail",
                  "Returning `head`, which is now the last node",
                  "Returning `node`, which is None"],
        nudge="The moment you write `node.next = prev`, the rest of the chain is "
              "unreachable. So save it one line earlier.",
        visual="A wave moves along the chain; behind it every arrow points back.",
        pseudocode="""
            prev = None
            while node:
                following = node.next
                node.next = prev
                prev = node
                node = following
            return prev
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-reverse", title="The Turned Chain", realm="twin_pointer_pass",
        difficulty="TUTORIAL", family="linked_reverse", pattern="TWO_POINTER",
        viz=VIZ_POINTERS, profile_weight=Q, result_adapter="linked", **chain,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Reversing a linked list is the single most frequently reported "
                   "linked-list screen.",
        statement="""
            Reverse the chain and return the new head. No new nodes: turn the links
            you were given.

            """ + LIST_SHAPE + """

            Same three cursors as the scaffold, from a blank screen this time. If you
            can write this without thinking, half of this realm is already yours.
        """,
        fn_name="reverse_list", params="head", reference=linked_ref(_ref_reverse),
        canonical="""
            def reverse_list(head):
                prev = None
                node = head
                while node is not None:
                    following = node.next     # save the rest before cutting the link
                    node.next = prev          # turn this arrow around
                    prev = node               # this node is now the reversed head
                    node = following
                return prev
        """,
        visible=[("four", [[1, 2, 3, 4]]), ("two", [[9, 8]])],
        hidden=[("six", [[1, 2, 3, 4, 5, 6]]), ("repeats", [[2, 2, 2]]),
                ("negatives", [[-5, 0, 5]]), ("longer", [list(range(12))])],
        edges=[("empty", [[]]), ("single", [[4]])],
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(n)", "O(n log n)", "O(n^2)"],
        failures=["Losing the tail by overwriting `.next` too early",
                  "Returning the wrong cursor at the end",
                  "Collecting the values into a list and building a whole new chain, "
                  "which works but answers a different question"],
        nudge="Three names, one loop, no new nodes.",
        visual="prev grows from the head end; node shrinks from the tail end.",
        pseudocode="""
            prev = None; node = head
            each step: save next, point node at prev, shuffle both cursors forward
            the answer is prev
        """,
        prerequisites=["ll-reverse-guided"], tags=["core", "linked-list", "classic"],
    ))

    P.append(rune(
        id="ll-reverse-rec-guided", title="The Rune That Calls Itself",
        realm="recursive_forest", difficulty="GUIDED", family="linked_reverse",
        pattern="RECURSION", scaffold_for="RECURSION: trust the smaller chain",
        secondary=["TWO_POINTER"], result_adapter="linked", **chain,
        statement="""
            Reverse the chain again, recursively this time, and return the new head.

            """ + LIST_SHAPE + """

            The recursive version is a single act of faith: assume the call on
            `head.next` comes back with everything after you already reversed. All
            that is left is your own node, which is now the very last one — so the
            node behind you must point at you, and you must point at nothing.

            Those are exactly the two missing runes.
        """,
        fn_name="reverse_recursive", params="head",
        reference=linked_ref(_ref_reverse),
        canonical="""
            def reverse_recursive(head):
                if head is None or head.next is None:
                    return head
                new_head = reverse_recursive(head.next)
                head.next.next = head
                head.next = None
                return new_head
        """,
        blanks=[("head.next.next = head",
                 "the node that used to follow me must now point back at me"),
                ("head.next = None", "and I am the new tail, so I point at nothing")],
        visible=[("three", [[1, 2, 3]]), ("two", [[4, 5]])],
        hidden=[("five", [[1, 2, 3, 4, 5]]), ("repeats", [[6, 6]]),
                ("negatives", [[-2, -1, 0]])],
        edges=[("empty", [[]]), ("single", [[8]])],
        failures=["Returning `head` instead of the head the recursion handed back",
                  "Forgetting `head.next = None`, which leaves a two-node ring",
                  "A base case of only `head is None`, which then dereferences None"],
        nudge="`new_head` is not your node. It came back from below and must be "
              "passed straight up, untouched.",
        visual="The recursion runs to the tail, then the fixes happen on the way back.",
        pseudocode="""
            empty or single -> return head
            new_head = reverse(head.next)
            head.next.next = head
            head.next = None
            return new_head
        """,
        time_complexity="O(n)", space_complexity="O(n)",
        prerequisites=["ll-reverse-guided"], tags=["core", "linked-list", "recursion"],
    ))

    P.append(code_problem(
        id="ll-reverse-rec", title="Faith in the Smaller Chain",
        realm="recursive_forest", difficulty="EASY", family="linked_reverse",
        pattern="RECURSION", secondary=["TWO_POINTER"], viz=VIZ_REC,
        profile_weight=Q, result_adapter="linked", **chain,
        statement="""
            Reverse the chain recursively and return the new head. Write the whole
            function.

            """ + LIST_SHAPE + """

            Two things have to be decided before you type anything: what the smallest
            chain you refuse to recurse on is, and which node the call returns. They
            are not the same node, and that is the entire difficulty.
        """,
        fn_name="reverse_recursive", params="head",
        reference=linked_ref(_ref_reverse),
        canonical="""
            def reverse_recursive(head):
                if head is None or head.next is None:
                    return head           # 0 or 1 nodes are already reversed
                new_head = reverse_recursive(head.next)
                head.next.next = head     # the node behind me turns around
                head.next = None          # and I become the tail
                return new_head           # the far end, unchanged all the way up
        """,
        visible=[("four", [[1, 2, 3, 4]]), ("two", [[1, 2]])],
        hidden=[("seven", [[1, 2, 3, 4, 5, 6, 7]]), ("repeats", [[3, 3, 3]]),
                ("negatives", [[-9, 9]]), ("longer", [list(range(15))])],
        edges=[("empty", [[]]), ("single", [[0]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Returning `head`, which is the tail of the reversed chain",
                  "Leaving `head.next` pointing forwards, producing a cycle",
                  "Recursing before checking for None"],
        nudge="Write the last two lines as a sentence first: 'the node after me now "
              "points at me, and I point at nothing'.",
        visual="Descend to the end; fix one link per frame on the way back up.",
        pseudocode="""
            base: 0 or 1 nodes -> head
            new_head = reverse(head.next)
            rewire head.next.next and head.next
            return new_head
        """,
        alternates=[{"name": "the iterative three-cursor loop",
                     "note": "O(1) space, and the one to reach for in a real timed practical.",
                     "complexity": "O(n) time, O(1) space"}],
        prerequisites=["ll-reverse-rec-guided"], tags=["core", "recursion"],
    ))

    P.append(code_problem(
        id="ll-reverse-between", title="Turning One Stretch of Road",
        realm="twin_pointer_pass", difficulty="MEDIUM", family="linked_reverse",
        pattern="TWO_POINTER", viz=VIZ_POINTERS, profile_weight=Q,
        result_adapter="linked", **chain,
        statement="""
            Reverse only the nodes from position `left` to position `right`,
            **counting from 1**, and return the head of the whole chain. Everything
            outside that stretch keeps its order.

            """ + LIST_SHAPE + """

            `left` and `right` are always valid positions in the chain, and
            `left <= right`. The trap is the node just before `left`: if `left` is 1
            there isn't one, which is what a dummy head is for.
        """,
        fn_name="reverse_between", params="head, left, right",
        reference=linked_ref(_ref_reverse_between),
        canonical="""
            def reverse_between(head, left, right):
                if head is None or left >= right:
                    return head
                dummy = ListNode(0, head)      # so 'the node before left' always exists
                before = dummy
                for _ in range(left - 1):
                    before = before.next
                tail = before.next             # ends up LAST in the reversed stretch
                node = tail.next
                for _ in range(right - left):
                    tail.next = node.next      # lift `node` out of the chain
                    node.next = before.next    # and splice it in at the front
                    before.next = node
                    node = tail.next
                return dummy.next
        """,
        visible=[("middle", [[1, 2, 3, 4, 5], 2, 4]), ("prefix", [[1, 2, 3, 4, 5], 1, 3])],
        hidden=[("whole list", [[1, 2, 3, 4], 1, 4]),
                ("suffix", [[1, 2, 3, 4, 5], 3, 5]),
                ("two nodes", [[1, 2], 1, 2]),
                ("repeats", [[5, 5, 6, 6], 2, 3])],
        edges=[("single position", [[1, 2, 3], 2, 2]), ("one node", [[9], 1, 1])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["No dummy head, so `left == 1` has no predecessor to rewire",
                  "Reconnecting the reversed stretch to the wrong two nodes",
                  "Off by one on the 1-based positions"],
        nudge="Name the two nodes that bracket the stretch before you touch anything "
              "inside it. Everything else is the reversal you already know.",
        visual="Cut out a segment, turn it, weld both seams back on.",
        pseudocode="""
            dummy -> head; walk `before` to position left - 1
            tail = first node of the stretch (it will end up last)
            repeat right - left times: lift the node after tail, splice after before
        """,
        prerequisites=["ll-reverse"], tags=["core", "linked-list", "classic"],
    ))

    P.append(code_problem(
        id="ll-swap-pairs", title="The Dance of Two", realm="twin_pointer_pass",
        difficulty="MEDIUM", family="linked_reverse", pattern="TWO_POINTER",
        secondary=["SIMULATION"], viz=VIZ_POINTERS, profile_weight=Q,
        result_adapter="linked", **chain,
        statement="""
            Swap every adjacent pair of nodes and return the new head. A final
            leftover node keeps its place.

            `[1, 2, 3, 4]` becomes `[2, 1, 4, 3]`; `[1, 2, 3]` becomes `[2, 1, 3]`.

            """ + LIST_SHAPE + """

            Swap the nodes, not the values. Swapping values is a one-liner that
            answers a question nobody asked.
        """,
        fn_name="swap_pairs", params="head", reference=linked_ref(_ref_swap_pairs),
        canonical="""
            def swap_pairs(head):
                dummy = ListNode(0, head)
                prev = dummy
                while prev.next is not None and prev.next.next is not None:
                    first = prev.next
                    second = first.next
                    first.next = second.next   # first now points past the pair
                    second.next = first        # second jumps in front of first
                    prev.next = second         # and the pair is hung back on
                    prev = first               # first is the new tail of the done part
                return dummy.next
        """,
        visible=[("four", [[1, 2, 3, 4]]), ("odd", [[1, 2, 3]])],
        hidden=[("two", [[1, 2]]), ("six", [[1, 2, 3, 4, 5, 6]]),
                ("repeats", [[7, 7, 8, 8]]), ("negatives", [[-1, -2, -3, -4]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Advancing `prev` to `second`, which is now behind `first`",
                  "Checking only `prev.next`, then dereferencing a missing partner",
                  "Swapping `.val` instead of relinking, which the examiner is "
                  "specifically watching for"],
        nudge="Three links change per pair, and the node you leave `prev` on is the "
              "one that ended up second.",
        visual="Each pair pivots in place; the chain either side is untouched.",
        pseudocode="""
            dummy -> head; prev = dummy
            while two nodes remain after prev:
                first, second = prev.next, prev.next.next
                relink first -> second.next, second -> first, prev -> second
                prev = first
        """,
        prerequisites=["ll-reverse"], tags=["core", "linked-list", "classic"],
    ))

    # == TWO WALKERS =========================================================

    P.append(rune(
        id="ll-middle-guided", title="The Rune of the Uneven Pace",
        realm="twin_pointer_pass", difficulty="GUIDED", family="fast_slow",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: fast and slow", **chain,
        statement="""
            Return the value of the middle node. When the chain has an even number of
            nodes, return the second of the two middles. An empty chain returns `None`.

            """ + LIST_SHAPE + """

            You could walk the chain twice: once to count, once to stop halfway. One
            pass is enough if you send two walkers at different speeds — when the fast
            one reaches the end, the slow one is exactly halfway.

            The two struck runes are the pace of the fast walker and the condition
            that keeps it from walking off the end.
        """,
        fn_name="middle_value", params="head", reference=linked_ref(_ref_middle),
        canonical="""
            def middle_value(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                return slow.val if slow is not None else None
        """,
        blanks=[("fast is not None and fast.next is not None",
                 "fast can still take a full two-node stride"),
                ("fast.next.next", "fast moves two nodes for every one of slow's")],
        visible=[("odd", [[1, 2, 3, 4, 5]]), ("even", [[1, 2, 3, 4]])],
        hidden=[("two", [[1, 2]]), ("six", [[1, 2, 3, 4, 5, 6]]),
                ("repeats", [[8, 8, 8]])],
        edges=[("empty", [[]]), ("single", [[3]])],
        failures=["Checking only `fast is not None`, then reading `fast.next.next` "
                  "off the end",
                  "Moving fast by one, which just reimplements slow"],
        nudge="Whatever fraction of the chain fast has covered, slow has covered half "
              "of it. That is the entire trick.",
        visual="Two runners on the same road, one at double speed.",
        pseudocode="""
            slow = fast = head
            while fast can move twice:
                slow += 1 node, fast += 2 nodes
            slow is the middle
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-middle", title="The Halfway Stone", realm="twin_pointer_pass",
        difficulty="TUTORIAL", family="fast_slow", pattern="TWO_POINTER",
        viz=VIZ_POINTERS, profile_weight=Q, **chain,
        statement="""
            Return the value of the middle node in a single pass, without counting the
            chain first. For an even count, return the second middle. Empty chain
            returns `None`.

            """ + LIST_SHAPE + """
        """,
        fn_name="middle_value", params="head", reference=linked_ref(_ref_middle),
        canonical="""
            def middle_value(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next          # one step
                    fast = fast.next.next     # two steps
                return slow.val if slow is not None else None
        """,
        visible=[("odd", [[10, 20, 30]]), ("even", [[10, 20, 30, 40]])],
        hidden=[("seven", [[1, 2, 3, 4, 5, 6, 7]]), ("two", [[5, 6]]),
                ("negatives", [[-3, -2, -1]]), ("longer", [list(range(10))])],
        edges=[("empty", [[]]), ("single", [[99]])],
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(n)", "O(n log n)", "O(n^2)"],
        failures=["Returning the first middle on an even chain",
                  "Two passes — correct, but not what was asked for"],
        nudge="One loop, two cursors, different strides.",
        visual="Fast falls off the end exactly when slow reaches the middle.",
        pseudocode="advance slow by 1 and fast by 2 while fast can still move twice",
        prerequisites=["ll-middle-guided"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-nth-from-end", title="Counting Back from the Edge",
        realm="twin_pointer_pass", difficulty="EASY", family="fast_slow",
        pattern="TWO_POINTER", viz=VIZ_POINTERS, profile_weight=Q, **chain,
        statement="""
            Return the value of the `n`-th node from the end, where `n = 1` is the
            last node. Return `None` if `n` is smaller than 1 or larger than the
            chain.

            """ + LIST_SHAPE + """

            You cannot walk backwards, and you are not allowed to count the chain
            first. Instead, start one walker `n` nodes ahead of the other and move
            them in lockstep: when the leader falls off the end, the follower is
            standing exactly where you want it.
        """,
        fn_name="nth_from_end", params="head, n",
        reference=linked_ref(_ref_nth_from_end),
        canonical="""
            def nth_from_end(head, n):
                if n < 1:
                    return None
                lead = head
                for _ in range(n):            # open a gap of exactly n nodes
                    if lead is None:
                        return None           # the chain is shorter than n
                    lead = lead.next
                trail = head
                while lead is not None:
                    lead = lead.next
                    trail = trail.next
                return trail.val if trail is not None else None
        """,
        visible=[("last", [[1, 2, 3, 4, 5], 1]), ("second from last", [[1, 2, 3, 4, 5], 2])],
        hidden=[("first", [[1, 2, 3], 3]), ("too far", [[1, 2, 3], 4]),
                ("zero", [[1, 2, 3], 0]), ("single", [[7], 1])],
        edges=[("empty", [[], 1]), ("negative n", [[1, 2], -1])],
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(n)", "O(n log n)", "O(n^2)"],
        failures=["A gap of n - 1 or n + 1 instead of n",
                  "Crashing instead of returning None when n exceeds the length",
                  "Counting the length first, which is two passes"],
        nudge="Fix the distance between the two cursors, then move them together. The "
              "distance is the answer.",
        visual="A rigid stick of length n slid along the chain until it hits the end.",
        pseudocode="""
            advance lead n nodes (bail out if the chain ends first)
            move lead and trail together until lead falls off
            trail is the answer
        """,
        prerequisites=["ll-middle"], tags=["core", "two-pointer"],
    ))

    P.append(rune(
        id="ll-cycle-guided", title="The Rune of the Closed Road",
        realm="twin_pointer_pass", difficulty="GUIDED", family="fast_slow",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: cycle detection",
        cmp="bool", **ring,
        statement="""
            Return `True` if the chain loops back on itself, `False` if it ends.

            A cyclic chain has no end, so `while node is not None` never stops. The
            fix is the same two walkers: if the road is a loop, the fast one laps the
            slow one and they land on the same node. If the road ends, the fast one
            falls off it.

            The tests describe each chain as `[values, pos]`, where `pos` is the index
            the last node links back to, or `-1` for no cycle — but your function is
            handed a real `ListNode`, exactly as it would be in a timed practical.
        """,
        fn_name="has_cycle", params="head", reference=linked_ref(_ref_has_cycle, cycle=True),
        canonical="""
            def has_cycle(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                    if slow is fast:
                        return True
                return False
        """,
        blanks=[("fast.next.next", "fast covers two nodes per round, slow covers one"),
                ("slow is fast", "the two walkers are standing on the same node")],
        visible=[("loop", [[[3, 2, 0, -4], 1]]), ("no loop", [[[1, 2, 3], -1]])],
        hidden=[("self loop", [[[1], 0]]), ("two node loop", [[[1, 2], 0]]),
                ("long tail into loop", [[[1, 2, 3, 4, 5, 6], 3]]),
                ("straight", [[[1], -1]])],
        edges=[("empty", [[[], -1]]), ("loop to last", [[[1, 2, 3], 2]])],
        failures=["`slow == fast`, which compares values and fires on any duplicate",
                  "Checking the meeting before either walker has moved, so every chain "
                  "reports a cycle",
                  "Using a set of node values instead of node identity"],
        nudge="`is`, not `==`. You are asking whether it is the same node, not whether "
              "it holds the same number.",
        visual="On a loop the fast runner eventually comes up behind the slow one.",
        pseudocode="""
            slow = fast = head
            while fast can move twice:
                move slow 1, fast 2
                if they are the same node: True
            False
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-middle-guided"], tags=["core", "linked-list", "classic"],
    ))

    P.append(code_problem(
        id="ll-has-cycle", title="The Road That Eats Its Own Tail",
        realm="twin_pointer_pass", difficulty="TUTORIAL", family="fast_slow",
        pattern="TWO_POINTER", cmp="bool", viz=VIZ_POINTERS, profile_weight=Q, **ring,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Floyd cycle detection is a long-standing screening archetype.",
        statement="""
            Return `True` if the chain contains a cycle, using O(1) extra memory.

            A set of visited nodes also works and is worth saying out loud — but it
            costs O(n) memory, and the two-walker version is what the question is
            actually about.

            Tests describe a chain as `[values, pos]`: `pos` is the index the last node
            links back to, `-1` for a chain that ends normally. Your function receives
            the head node.
        """,
        fn_name="has_cycle", params="head",
        reference=linked_ref(_ref_has_cycle, cycle=True),
        canonical="""
            def has_cycle(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                    if slow is fast:          # identity, not equality
                        return True
                return False
        """,
        visible=[("loop", [[[1, 2, 3, 4], 2]]), ("no loop", [[[1, 2, 3, 4], -1]])],
        hidden=[("self loop", [[[5], 0]]), ("whole list loops", [[[1, 2, 3], 0]]),
                ("duplicate values, no loop", [[[1, 1, 1, 1], -1]]),
                ("long", [[list(range(30)), 10]])],
        edges=[("empty", [[[], -1]]), ("single, no loop", [[[1], -1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        complexity_choices=["O(1)", "O(n)", "O(n log n)", "O(n^2)"],
        failures=["Comparing values with `==` — `[1, 1, 1]` then reports a cycle",
                  "Returning True when the two cursors start equal",
                  "Forgetting that `fast.next` can be None halfway through the stride"],
        nudge="The chain either ends or it does not. If it does, fast finds the end "
              "first; if it does not, fast finds slow.",
        visual="Two runners on a ring: the faster one must eventually lap the slower.",
        pseudocode="""
            slow = fast = head
            loop while fast and fast.next:
                slow 1 step, fast 2 steps
                same node -> True
            -> False
        """,
        alternates=[{"name": "a set of visited node identities",
                     "note": "Simpler to explain, O(n) memory. Say it, then improve it.",
                     "complexity": "O(n) time, O(n) space"}],
        prerequisites=["ll-cycle-guided"], tags=["core", "two-pointer", "classic"],
    ))

    P.append(code_problem(
        id="ll-cycle-length", title="Measuring the Ring", realm="twin_pointer_pass",
        difficulty="EASY", family="fast_slow", pattern="TWO_POINTER",
        viz=VIZ_POINTERS, profile_weight=Q, **ring,
        statement="""
            Return the number of nodes in the cycle, or `0` if the chain has none.

            Chains arrive as `[values, pos]`, `pos` being the index the tail links back
            to. Your function receives the head node.

            Once the two walkers meet, they are both standing somewhere on the ring.
            That is enough: walk one of them around until it comes back to itself and
            count the steps.
        """,
        fn_name="cycle_length", params="head",
        reference=linked_ref(_ref_cycle_length, cycle=True),
        canonical="""
            def cycle_length(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                    if slow is fast:
                        length = 1
                        runner = slow.next
                        while runner is not slow:    # one lap of the ring
                            runner = runner.next
                            length += 1
                        return length
                return 0
        """,
        visible=[("four ring", [[[1, 2, 3, 4], 0]]), ("no ring", [[[1, 2, 3], -1]])],
        hidden=[("tail into a ring of two", [[[1, 2, 3, 4], 2]]),
                ("self loop", [[[1], 0]]),
                ("long tail, small ring", [[list(range(10)), 8]]),
                ("ring of three", [[[1, 2, 3, 4, 5, 6], 3]])],
        edges=[("empty", [[[], -1]]), ("single, no ring", [[[7], -1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Starting the count at 0 and returning one less than the ring",
                  "Counting from `head` instead of from the meeting point",
                  "Returning the distance to the ring rather than its size"],
        nudge="The meeting point is on the ring. Anything on a ring gets back to "
              "itself, and the count of steps is the size.",
        visual="Drop a marker where they meet, walk one lap, count.",
        pseudocode="""
            find the meeting node with fast/slow
            walk from meeting.next until you are back at meeting, counting
        """,
        prerequisites=["ll-has-cycle"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-cycle-entry", title="Where the Road Closed", realm="twin_pointer_pass",
        difficulty="MEDIUM", family="fast_slow", pattern="TWO_POINTER",
        viz=VIZ_POINTERS, profile_weight=Q, boss=True, **ring,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Cycle entry — 'Linked List Cycle II' — is a repeatedly reported "
                   "follow-up to plain cycle detection.",
        statement="""
            Return the value of the node where the cycle begins, or `None` if the
            chain has no cycle. All values in a chain are distinct.

            Chains arrive as `[values, pos]`, `pos` being the index the tail links back
            to. Your function receives the head node.

            There is a fact here worth knowing rather than deriving under pressure:
            after fast and slow meet, the distance from the head to the entry equals
            the distance from the meeting point to the entry. So restart one walker at
            the head, move both one step at a time, and they meet at the entry.
        """,
        fn_name="cycle_entry_value", params="head",
        reference=linked_ref(_ref_cycle_entry, cycle=True),
        canonical="""
            def cycle_entry_value(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                    if slow is fast:
                        finder = head
                        while finder is not slow:   # both move ONE step now
                            finder = finder.next
                            slow = slow.next
                        return finder.val
                return None
        """,
        visible=[("enters at index 1", [[[3, 2, 0, -4], 1]]),
                 ("no cycle", [[[1, 2, 3], -1]])],
        hidden=[("enters at head", [[[1, 2, 3, 4], 0]]),
                ("self loop", [[[9], 0]]),
                ("long tail", [[list(range(12)), 7]]),
                ("enters at the last node", [[[1, 2, 3], 2]])],
        edges=[("empty", [[[], -1]]), ("single, no cycle", [[[5], -1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Returning the meeting point, which is almost never the entry",
                  "Moving the second walker two steps in the finding phase",
                  "Forgetting that a cycle entering at the head is still a cycle"],
        nudge="Detection is phase one and you already have it. Phase two starts a "
              "fresh cursor at the head and walks both at the same speed.",
        visual="Two equal distances meeting at the mouth of the ring.",
        pseudocode="""
            phase 1: fast/slow until they meet (or no cycle -> None)
            phase 2: finder = head; advance finder and slow one step each
                     until they are the same node -> that is the entry
        """,
        alternates=[{"name": "a set of visited node identities, first repeat wins",
                     "note": "O(n) memory and much easier to justify on a whiteboard.",
                     "complexity": "O(n) time, O(n) space"}],
        prerequisites=["ll-has-cycle"], tags=["core", "two-pointer", "classic", "boss"],
    ))

    P.append(code_problem(
        id="ll-remove-nth-end", title="Cutting Back from the Edge",
        realm="twin_pointer_pass", difficulty="MEDIUM", family="fast_slow",
        pattern="TWO_POINTER", secondary=["SIMULATION"], viz=VIZ_POINTERS,
        profile_weight=Q, result_adapter="linked", **chain,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Removing the n-th node from the end in one pass is a repeatedly "
                   "reported archetype.",
        statement="""
            Remove the `n`-th node from the end and return the head. `n = 1` is the
            last node. If `n` is smaller than 1 or larger than the chain, change
            nothing.

            """ + LIST_SHAPE + """

            One pass. The gap trick from `nth_from_end` gets you to the right node —
            but to *remove* it you have to be standing on the node **before** it, and
            when the removed node is the head there is no node before it. That is what
            a dummy head is for.
        """,
        fn_name="remove_nth_from_end", params="head, n",
        reference=linked_ref(_ref_remove_nth_from_end),
        canonical="""
            def remove_nth_from_end(head, n):
                if head is None or n < 1:
                    return head
                dummy = ListNode(0, head)      # a node that always precedes the target
                lead = dummy
                for _ in range(n):
                    if lead.next is None:
                        return head            # n is longer than the chain
                    lead = lead.next
                trail = dummy
                while lead.next is not None:
                    lead = lead.next
                    trail = trail.next
                trail.next = trail.next.next   # unlink the node in front of trail
                return dummy.next
        """,
        visible=[("middle", [[1, 2, 3, 4, 5], 2]), ("last", [[1, 2, 3], 1])],
        hidden=[("head", [[1, 2, 3], 3]), ("only node", [[9], 1]),
                ("past the end", [[1, 2], 5]), ("zero", [[1, 2, 3], 0]),
                ("repeats", [[4, 4, 4], 2])],
        edges=[("empty", [[], 1]), ("negative", [[1, 2], -3])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Stopping on the target instead of on its predecessor",
                  "No dummy head, so removing the first node needs a special case that "
                  "is usually written wrong",
                  "Crashing when n exceeds the length"],
        nudge="You can only delete a node by rewiring the one before it. Make sure "
              "there is always one before it.",
        visual="A stick of length n slid to the end; the follower stops one short.",
        pseudocode="""
            dummy -> head
            lead walks n nodes from dummy (bail if the chain is shorter)
            move lead and trail together until lead is the last node
            trail.next = trail.next.next
        """,
        prerequisites=["ll-nth-from-end"], tags=["core", "two-pointer", "classic"],
    ))

    # == MERGING =============================================================

    P.append(rune(
        id="ll-merge-guided", title="The Rune of the Braided Chains",
        realm="twin_pointer_pass", difficulty="GUIDED", family="merge",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: merging two sorted runs",
        result_adapter="linked", **pair,
        statement="""
            `a` and `b` are each already sorted ascending. Weave them into one sorted
            chain and return its head. Reuse the nodes you were given.

            `a` and `b` are `ListNode` heads, either of which may be `None`.

            The shape is a dummy head plus a tail cursor: repeatedly take whichever
            of the two front nodes is smaller and hang it off the tail. Two runes are
            missing — the comparison that decides which side to take, and the line
            that deals with whatever is left over when one side runs dry.
        """,
        fn_name="merge_sorted", params="a, b",
        reference=linked_ref(_ref_merge_sorted, heads=2),
        canonical="""
            def merge_sorted(a, b):
                dummy = ListNode(0)
                tail = dummy
                while a is not None and b is not None:
                    if a.val <= b.val:
                        tail.next = a
                        a = a.next
                    else:
                        tail.next = b
                        b = b.next
                    tail = tail.next
                tail.next = a if a is not None else b
                return dummy.next
        """,
        blanks=[("a.val <= b.val", "take from `a` while its head is not the larger one"),
                ("a if a is not None else b",
                 "whichever chain still has nodes; it is already sorted, so attach it whole")],
        visible=[("interleaved", [[1, 3, 5], [2, 4, 6]]),
                 ("one runs out early", [[1, 2], [3, 4, 5]])],
        hidden=[("equal values", [[1, 1], [1, 1]]),
                ("all of a first", [[1, 2, 3], [9]]),
                ("negatives", [[-5, -1], [-3, 0]])],
        edges=[("a empty", [[], [1, 2]]), ("both empty", [[], []])],
        constraints=["both inputs are sorted ascending"],
        failures=["Appending the remainder one node at a time, or forgetting it entirely",
                  "Using `<` instead of `<=`, which is not wrong but is not stable",
                  "Advancing `tail` before you have hung anything on it"],
        nudge="At every step only two nodes are candidates: the front of each chain.",
        visual="A zip closing: one tooth from the left, one from the right, whichever "
               "is smaller.",
        pseudocode="""
            dummy, tail = dummy
            while both chains have a head:
                attach the smaller head, advance that chain, advance tail
            attach whatever remains
        """,
        time_complexity="O(n + m)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list", "merge"],
    ))

    P.append(code_problem(
        id="ll-merge-two", title="Two Roads Made One", realm="twin_pointer_pass",
        difficulty="TUTORIAL", family="merge", pattern="TWO_POINTER",
        viz=VIZ_POINTERS, profile_weight=Q, result_adapter="linked", **pair,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Merging two sorted lists is among the most frequently reported "
                   "warm-up questions.",
        statement="""
            Merge two sorted chains into one sorted chain and return its head. Do not
            build new nodes, and do not collect the values into a Python list and sort
            them — the point is the weave.

            `a` and `b` are `ListNode` heads; either may be `None`.
        """,
        fn_name="merge_sorted", params="a, b",
        reference=linked_ref(_ref_merge_sorted, heads=2),
        canonical="""
            def merge_sorted(a, b):
                dummy = ListNode(0)      # saves an 'is this the first node?' branch
                tail = dummy
                while a is not None and b is not None:
                    if a.val <= b.val:
                        tail.next, a = a, a.next
                    else:
                        tail.next, b = b, b.next
                    tail = tail.next
                tail.next = a if a is not None else b   # one side is already sorted
                return dummy.next
        """,
        visible=[("classic", [[1, 2, 4], [1, 3, 4]]), ("disjoint", [[1, 2], [8, 9]])],
        hidden=[("b first", [[5, 6], [1, 2]]), ("equal heads", [[2, 2], [2, 2]]),
                ("uneven lengths", [[1], [2, 3, 4, 5, 6]]),
                ("negatives", [[-9, -1], [-5, 0, 3]])],
        edges=[("a empty", [[], [1]]), ("b empty", [[1], []]),
               ("both empty", [[], []])],
        time_complexity="O(n + m)", space_complexity="O(1)",
        failures=["Dropping the tail of the longer chain",
                  "Building a whole new chain of new nodes",
                  "Special-casing the first node instead of using a dummy head"],
        nudge="A dummy head exists so that 'attach the first node' and 'attach the "
              "fortieth node' are the same line of code.",
        visual="Two sorted queues, one server, always taking the smaller front.",
        pseudocode="""
            dummy; tail = dummy
            while a and b: attach smaller, advance
            attach the survivor
            return dummy.next
        """,
        prerequisites=["ll-merge-guided"], tags=["core", "merge", "classic"],
    ))

    P.append(code_problem(
        id="ll-merge-alternate", title="The Braid", realm="twin_pointer_pass",
        difficulty="EASY", family="merge", pattern="TWO_POINTER",
        secondary=["SIMULATION"], viz=VIZ_POINTERS, profile_weight=Q,
        result_adapter="linked", **pair,
        statement="""
            Weave the two chains together by alternating nodes, starting with `a`:
            `a0, b0, a1, b1, ...`. When one chain runs out, the rest of the other
            follows in order. Neither chain is sorted and neither needs to be.

            `a` and `b` are `ListNode` heads; either may be `None`.

            This is the merge you just wrote with the comparison removed, which is
            worth noticing: the loop shape is the same, only the choice rule changed.
        """,
        fn_name="alternate_merge", params="a, b",
        reference=linked_ref(_ref_alternate, heads=2),
        canonical="""
            def alternate_merge(a, b):
                dummy = ListNode(0)
                tail = dummy
                while a is not None and b is not None:
                    tail.next = a
                    a = a.next
                    tail = tail.next
                    tail.next = b
                    b = b.next
                    tail = tail.next
                tail.next = a if a is not None else b
                return dummy.next
        """,
        visible=[("equal lengths", [[1, 2, 3], [7, 8, 9]]),
                 ("a is longer", [[1, 2, 3, 4], [9]])],
        hidden=[("b is longer", [[1], [7, 8, 9]]),
                ("repeats", [[5, 5], [5, 5]]),
                ("negatives", [[-1, -2], [-3, -4]])],
        edges=[("a empty", [[], [1, 2]]), ("b empty", [[1, 2], []]),
               ("both empty", [[], []])],
        time_complexity="O(n + m)", space_complexity="O(1)",
        failures=["Advancing the source chain after attaching the node from the other one",
                  "Leaving the remainder unattached",
                  "Starting with `b`"],
        nudge="Attach, advance the source, advance the tail. Twice per round.",
        visual="Left, right, left, right, then whatever is left over.",
        pseudocode="""
            while both chains have nodes: attach a's head, then b's head
            attach the survivor
        """,
        prerequisites=["ll-merge-two"], tags=["core", "merge"],
    ))

    P.append(code_problem(
        id="ll-merge-three", title="Three Rivers", realm="twin_pointer_pass",
        difficulty="MEDIUM", family="merge", pattern="TWO_POINTER",
        secondary=["HEAP", "SORTING"], viz=VIZ_POINTERS, profile_weight=Q,
        result_adapter="linked", preamble=PREAMBLE,
        arg_adapters=["linked", "linked", "linked"],
        starter_hint="a, b and c are ListNode heads; any of them may be None",
        statement="""
            Merge three sorted chains into one sorted chain and return its head. Any
            of them may be `None`.

            The honest answer is that you already solved this: merge two, then merge
            the result with the third. Say that out loud before you write anything
            clever, and then say what it costs — because 'merge k sorted lists' is the
            same question with a heap bolted on, and the examiner is listening for
            whether you know why the heap is there.
        """,
        fn_name="merge_three", params="a, b, c",
        reference=linked_ref(_ref_merge_three, heads=3),
        canonical="""
            def merge_three(a, b, c):
                def merge(x, y):
                    dummy = ListNode(0)
                    tail = dummy
                    while x is not None and y is not None:
                        if x.val <= y.val:
                            tail.next, x = x, x.next
                        else:
                            tail.next, y = y, y.next
                        tail = tail.next
                    tail.next = x if x is not None else y
                    return dummy.next

                return merge(merge(a, b), c)     # pairwise, reusing the solved case
        """,
        visible=[("three runs", [[1, 4], [2, 5], [3, 6]]),
                 ("one empty", [[1, 2], [], [3]])],
        hidden=[("all equal", [[2], [2], [2]]),
                ("very uneven", [[1, 2, 3, 4, 5], [6], []]),
                ("negatives", [[-9, -2], [-5], [-1, 0]]),
                ("descending sizes", [[1, 5, 9], [2, 6], [3]])],
        edges=[("all empty", [[], [], []]), ("only c", [[], [], [7, 8]])],
        time_complexity="O(n + m + k)", space_complexity="O(1)",
        failures=["Concatenating and sorting, which throws away the fact that the "
                  "inputs were already sorted",
                  "Writing the two-way merge a second and third time instead of "
                  "calling it",
                  "Assuming none of the three is empty"],
        nudge="Solve it with the function you already have. The interesting part is "
              "what you say about doing this for k chains instead of three.",
        visual="Two confluences, one after the other.",
        pseudocode="""
            merge(x, y) is the two-way weave you already wrote
            answer = merge(merge(a, b), c)
        """,
        alternates=[{"name": "a min-heap of the k current heads",
                     "note": "O(N log k) for k chains, and the reason the k-way version "
                             "is a different question.",
                     "complexity": "O(N log k)"}],
        prerequisites=["ll-merge-two"], tags=["core", "merge", "classic"],
    ))

    # == EDITING THE CHAIN ===================================================

    P.append(rune(
        id="ll-remove-guided", title="The Rune of the Severed Link",
        realm="array_caverns", difficulty="GUIDED", family="linked_edit",
        pattern="SIMULATION", scaffold_for="LINKED LIST: deletion by rewiring",
        result_adapter="linked", **chain,
        statement="""
            Remove every node whose value equals `target` and return the head.

            """ + LIST_SHAPE + """

            You never delete a node directly. You delete it by making the node before
            it point past it — which means the awkward case is the first node, since
            nothing comes before it. A dummy head in front of the chain makes that
            case disappear.

            Two runes are missing: the rewiring that skips a node, and the advance
            that must only happen when you did *not* remove anything.
        """,
        fn_name="remove_value", params="head, target",
        reference=linked_ref(_ref_remove_value),
        canonical="""
            def remove_value(head, target):
                dummy = ListNode(0, head)
                node = dummy
                while node.next is not None:
                    if node.next.val == target:
                        node.next = node.next.next
                    else:
                        node = node.next
                return dummy.next
        """,
        blanks=[("node.next = node.next.next",
                 "point past the doomed node, which unlinks it"),
                ("node = node.next",
                 "step forward — but only when nothing was removed")],
        visible=[("middle", [[1, 2, 6, 3], 6]), ("none match", [[1, 2, 3], 9])],
        hidden=[("head matches", [[6, 1, 2], 6]),
                ("run of matches", [[7, 7, 7, 1], 7]),
                ("tail matches", [[1, 2, 7], 7]),
                ("all match", [[4, 4, 4], 4])],
        edges=[("empty", [[], 1]), ("single match", [[5], 5])],
        failures=["Advancing after a removal, which skips the node that slid into place",
                  "No dummy head, so a matching first node survives",
                  "Losing the rest of the chain by assigning `node.next` twice"],
        nudge="After you unlink a node, the next candidate is already sitting at "
              "`node.next`. Do not walk past it.",
        visual="A cursor that stays put whenever it deletes, and only moves when it "
               "does not.",
        pseudocode="""
            dummy -> head; node = dummy
            while there is a node ahead:
                it matches -> skip over it
                otherwise  -> advance
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-remove-value", title="Cutting the Named Link", realm="array_caverns",
        difficulty="TUTORIAL", family="linked_edit", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, result_adapter="linked", **chain,
        statement="""
            Remove every node equal to `target` and return the head of what is left.
            Removing everything leaves `None`.

            """ + LIST_SHAPE + """

            Write the whole function. If you find yourself writing a special case for
            the first node, stop and add a dummy head instead.
        """,
        fn_name="remove_value", params="head, target",
        reference=linked_ref(_ref_remove_value),
        canonical="""
            def remove_value(head, target):
                dummy = ListNode(0, head)
                node = dummy
                while node.next is not None:
                    if node.next.val == target:
                        node.next = node.next.next   # unlink, do NOT advance
                    else:
                        node = node.next
                return dummy.next
        """,
        visible=[("two matches", [[1, 2, 6, 3, 6], 6]), ("none", [[1, 2, 3], 4])],
        hidden=[("leading run", [[7, 7, 1, 2], 7]), ("everything", [[3, 3, 3], 3]),
                ("only the tail", [[1, 2, 3], 3]),
                ("negatives", [[-1, -2, -1], -1])],
        edges=[("empty", [[], 0]), ("single non-match", [[5], 9])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Advancing the cursor after a deletion",
                  "Handling a matching head with a `while head and head.val == target` "
                  "prologue and then forgetting it in the loop",
                  "Returning `head` rather than `dummy.next`"],
        nudge="One cursor, always standing *behind* the node it is judging.",
        visual="Each survivor is spliced onto the previous survivor.",
        pseudocode="""
            dummy in front; cursor at dummy
            match ahead -> splice it out; else -> step
            return dummy.next
        """,
        prerequisites=["ll-remove-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-dedupe-sorted", title="The Stutter in the Chain",
        realm="array_caverns", difficulty="EASY", family="linked_edit",
        pattern="SIMULATION", viz=VIZ_CHAIN, profile_weight=Q,
        result_adapter="linked", **chain,
        statement="""
            The chain is sorted ascending. Remove the repeats so every value appears
            exactly once, keeping the first of each run, and return the head.

            `[1, 1, 2, 3, 3]` becomes `[1, 2, 3]`.

            """ + LIST_SHAPE + """

            Because the chain is sorted, duplicates are always adjacent, and that is
            the whole reason this is easier than the unsorted version: you never need
            to remember anything.
        """,
        fn_name="remove_duplicates", params="head",
        reference=linked_ref(_ref_dedupe_sorted),
        canonical="""
            def remove_duplicates(head):
                node = head
                while node is not None and node.next is not None:
                    if node.next.val == node.val:
                        node.next = node.next.next   # drop the repeat, stay put
                    else:
                        node = node.next
                return head
        """,
        visible=[("one repeat", [[1, 1, 2]]), ("several runs", [[1, 1, 2, 3, 3]])],
        hidden=[("all identical", [[4, 4, 4, 4]]), ("no repeats", [[1, 2, 3]]),
                ("repeat at the end", [[1, 2, 2]]),
                ("negatives", [[-2, -2, -1, 0, 0]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        constraints=["the chain is sorted ascending"],
        failures=["Advancing after removing, which misses three-in-a-row",
                  "Comparing `node.val` to `node.next.next.val`",
                  "Needing a dummy head — you do not, because the first node always "
                  "survives"],
        nudge="Sorted means equal values are neighbours. You only ever compare a node "
              "to the one directly after it.",
        visual="Collapse each run of equal values down to its first node.",
        pseudocode="""
            node = head
            while node and node.next:
                same value ahead -> splice it out
                otherwise        -> advance
            return head
        """,
        prerequisites=["ll-remove-value"], tags=["core", "linked-list", "classic"],
    ))

    P.append(code_problem(
        id="ll-remove-all-dups", title="No Second Chances", realm="array_caverns",
        difficulty="MEDIUM", family="linked_edit", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, result_adapter="linked", **chain,
        statement="""
            The chain is sorted ascending. Remove **every** node whose value appears
            more than once — not just the repeats, the originals too — and return the
            head.

            `[1, 2, 3, 3, 4, 4, 5]` becomes `[1, 2, 5]`.

            """ + LIST_SHAPE + """

            Now the first node can disappear, so the dummy head is back. And a run can
            be any length, so you have to consume the whole run before you decide what
            to reattach.
        """,
        fn_name="delete_all_duplicates", params="head",
        reference=linked_ref(_ref_delete_all_duplicates),
        canonical="""
            def delete_all_duplicates(head):
                dummy = ListNode(0, head)
                prev = dummy                      # last node known to be unique
                node = head
                while node is not None:
                    if node.next is not None and node.next.val == node.val:
                        value = node.val
                        while node is not None and node.val == value:
                            node = node.next      # skip the entire run
                        prev.next = node
                    else:
                        prev = node
                        node = node.next
                return dummy.next
        """,
        visible=[("two runs", [[1, 2, 3, 3, 4, 4, 5]]), ("head is a run", [[1, 1, 2, 3]])],
        hidden=[("everything repeats", [[1, 1, 2, 2]]),
                ("nothing repeats", [[1, 2, 3]]),
                ("triple", [[1, 1, 1, 2]]),
                ("tail run", [[1, 2, 2]]),
                ("all identical", [[7, 7, 7]])],
        edges=[("empty", [[]]), ("single", [[3]])],
        constraints=["the chain is sorted ascending"],
        failures=["Keeping one copy of each duplicated value — that is the easier "
                  "problem, and it is not this one",
                  "Reattaching before the run has been fully consumed",
                  "Advancing `prev` into a node that is about to be deleted"],
        nudge="`prev` must only ever point at a node you are certain survives.",
        visual="Runs of length one are kept whole; runs of length two or more vanish.",
        pseudocode="""
            dummy; prev = dummy; node = head
            while node:
                duplicate run ahead -> skip the whole run, prev.next = node
                otherwise           -> prev = node; node = node.next
        """,
        prerequisites=["ll-dedupe-sorted"], tags=["core", "linked-list", "classic"],
    ))

    P.append(code_problem(
        id="ll-dedupe-unsorted", title="The Chain That Remembers",
        realm="array_caverns", difficulty="MEDIUM", family="linked_edit",
        pattern="HASH_MAP", secondary=["SET", "SIMULATION"], viz=VIZ_MAP,
        profile_weight=Q, result_adapter="linked", **chain,
        statement="""
            The chain is **not** sorted. Keep the first occurrence of each value and
            remove every later one. Return the head.

            `[1, 3, 2, 3, 1]` becomes `[1, 3, 2]`.

            """ + LIST_SHAPE + """

            Unsorted means duplicates are no longer neighbours, so the chain can no
            longer tell you what it has already shown you. Something else has to
            remember — and the follow-up an examiner will ask is how you would do
            it with no extra memory at all.
        """,
        fn_name="remove_duplicates_unsorted", params="head",
        reference=linked_ref(_ref_dedupe_unsorted),
        canonical="""
            def remove_duplicates_unsorted(head):
                seen = set()
                dummy = ListNode(0, head)
                prev = dummy
                node = head
                while node is not None:
                    if node.val in seen:
                        prev.next = node.next     # unlink; prev does not move
                    else:
                        seen.add(node.val)
                        prev = node
                    node = node.next
                return dummy.next
        """,
        visible=[("two repeats", [[1, 3, 2, 3, 1]]), ("none", [[1, 2, 3]])],
        hidden=[("all identical", [[5, 5, 5]]),
                ("repeat at the head", [[2, 1, 2]]),
                ("negatives", [[-1, 1, -1, 1]]),
                ("longer", [[4, 1, 4, 2, 1, 3, 2]])],
        edges=[("empty", [[]]), ("single", [[8]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Moving `prev` after a deletion, which loses the link",
                  "Using a set of nodes instead of a set of values",
                  "Sorting first, which destroys the required order"],
        nudge="The set is the memory the chain does not have. Everything else is the "
              "deletion loop you already know.",
        visual="A ledger of values seen so far; anything already in it gets spliced out.",
        pseudocode="""
            seen = set(); dummy; prev = dummy
            for each node:
                value in seen -> prev.next = node.next
                else          -> record it, prev = node
        """,
        alternates=[{"name": "for each node, scan the rest of the chain and delete matches",
                     "note": "O(1) memory, O(n^2) time — the standard follow-up.",
                     "complexity": "O(n^2) time, O(1) space"}],
        prerequisites=["ll-dedupe-sorted"], tags=["core", "hash-map", "classic"],
    ))

    P.append(code_problem(
        id="ll-partition", title="The Sorting Gate", realm="array_caverns",
        difficulty="MEDIUM", family="linked_edit", pattern="SIMULATION",
        secondary=["TWO_POINTER"], viz=VIZ_CHAIN, profile_weight=Q,
        result_adapter="linked", **chain,
        statement="""
            Rearrange the chain so every node with a value less than `x` comes before
            every node with a value greater than or equal to `x`, and return the head.
            Within each group the original relative order must be preserved.

            `[1, 4, 3, 2, 5, 2]` with `x = 3` becomes `[1, 2, 2, 4, 3, 5]`.

            """ + LIST_SHAPE + """

            Order-preserving is the constraint that rules out the obvious swap-based
            approach. Build two chains instead, then join them.
        """,
        fn_name="partition", params="head, x", reference=linked_ref(_ref_partition),
        canonical="""
            def partition(head, x):
                low = ListNode(0)          # dummy head for the 'less than x' chain
                high = ListNode(0)         # dummy head for the rest
                low_tail, high_tail = low, high
                node = head
                while node is not None:
                    if node.val < x:
                        low_tail.next = node
                        low_tail = node
                    else:
                        high_tail.next = node
                        high_tail = node
                    node = node.next
                high_tail.next = None      # the old tail may still point backwards
                low_tail.next = high.next
                return low.next
        """,
        visible=[("mixed", [[1, 4, 3, 2, 5, 2], 3]), ("already split", [[1, 2, 5, 6], 3])],
        hidden=[("all below", [[1, 2], 5]), ("all at or above", [[5, 6], 3]),
                ("equal to x", [[3, 1, 3], 3]),
                ("negatives", [[-1, 4, -3], 0]),
                ("reverse order", [[6, 5, 4, 1], 5])],
        edges=[("empty", [[], 3]), ("single", [[1], 1])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Forgetting `high_tail.next = None`, which leaves a cycle",
                  "Swapping values, which cannot preserve relative order in general",
                  "Joining the chains in the wrong direction"],
        nudge="Two dummy heads, two tails, one pass. The only subtle line is the one "
              "that terminates the second chain.",
        visual="A gate with two hoppers; everything falls into one of them in arrival "
               "order, then the hoppers are stacked.",
        pseudocode="""
            low/high dummy heads with tails
            for each node: append to low if val < x else to high
            terminate high; low_tail.next = high.next
            return low.next
        """,
        prerequisites=["ll-remove-value"], tags=["core", "linked-list", "classic"],
    ))

    # == DIGITS IN A CHAIN ===================================================

    P.append(rune(
        id="ll-digits-guided", title="The Rune of Place and Value",
        realm="array_caverns", difficulty="GUIDED", family="linked_arith",
        pattern="SIMULATION", scaffold_for="LINKED LIST: digits and carries", **chain,
        statement="""
            The chain holds the decimal digits of a non-negative number **in reverse**:
            the head is the ones column, then tens, then hundreds. Return the number.

            `[2, 4, 3]` is `342`. An empty chain is `0`.

            """ + LIST_SHAPE + """

            Reverse order looks perverse until you notice it is the order arithmetic
            actually works in: you add from the ones column upward, and so does every
            problem after this one. Two runes are missing, and both concern the column
            a digit is sitting in.
        """,
        fn_name="digits_to_number", params="head",
        reference=linked_ref(_ref_digits_to_number),
        canonical="""
            def digits_to_number(head):
                total = 0
                place = 1
                node = head
                while node is not None:
                    total += node.val * place
                    place *= 10
                    node = node.next
                return total
        """,
        blanks=[("node.val * place", "this digit, scaled to the column it sits in"),
                ("place *= 10", "the next node along is worth ten times this one")],
        visible=[("three digits", [[2, 4, 3]]), ("one digit", [[7]])],
        hidden=[("trailing zeros in the number", [[0, 0, 1]]),
                ("zero", [[0]]), ("all nines", [[9, 9, 9]]),
                ("longer", [[1, 2, 3, 4, 5]])],
        edges=[("empty", [[]])],
        constraints=["digits are 0-9, stored least significant first"],
        failures=["Reading the chain as if the head were the most significant digit",
                  "Multiplying the running total by 10 instead of tracking the place"],
        nudge="The head is the ones column. Every step forward multiplies the column "
              "value by ten.",
        visual="1, 10, 100, 1000 — one column per node.",
        pseudocode="""
            total = 0; place = 1
            for each node: total += digit * place; place *= 10
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-number-to-digits", title="Breaking a Number Into Links",
        realm="array_caverns", difficulty="TUTORIAL", family="linked_arith",
        pattern="SIMULATION", viz=VIZ_CHAIN, profile_weight=Q,
        preamble=PREAMBLE, arg_adapters=[], result_adapter="linked",
        starter_hint="return the head of a chain of digits, ones column first",
        statement="""
            Given a non-negative integer `number`, build the reverse-order digit chain
            for it and return the head. `342` becomes `[2, 4, 3]`; `0` becomes `[0]`.

            `ListNode(val, next)` is already defined.

            `number % 10` is the ones digit and `number // 10` is everything else, so
            the digits come out in exactly the order the chain wants them. The only
            trap is zero, which must still produce one node.
        """,
        fn_name="number_to_digits", params="number", reference=_ref_number_to_digits,
        canonical="""
            def number_to_digits(number):
                head = None
                tail = None
                while True:                      # run at least once, so 0 -> [0]
                    node = ListNode(number % 10)
                    if head is None:
                        head = node
                    else:
                        tail.next = node
                    tail = node
                    number //= 10
                    if number == 0:
                        break
                return head
        """,
        visible=[("three digits", [342]), ("one digit", [7])],
        hidden=[("zero", [0]), ("round number", [1000]),
                ("all nines", [999]), ("long", [123456789])],
        edges=[("nine", [9]), ("ten", [10])],
        constraints=["0 <= number"],
        time_complexity="O(d)", space_complexity="O(d)",
        failures=["A `while number > 0` loop, which returns None for 0",
                  "Building the digits most significant first",
                  "Returning the tail"],
        nudge="`% 10` then `// 10`, and make sure the loop body runs at least once.",
        visual="Peel the ones column off, hang it on the chain, repeat.",
        pseudocode="""
            repeat:
                append node(number % 10)
                number //= 10
            until number == 0
        """,
        prerequisites=["ll-digits-guided", "ll-build"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-add-one", title="One More Than the Chain", realm="array_caverns",
        difficulty="EASY", family="linked_arith", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, result_adapter="linked", **chain,
        statement="""
            The chain holds a non-negative number's digits in reverse, ones column
            first. Add one to it and return the head of the result chain. An empty
            chain counts as `0`, so it becomes `[1]`.

            `[9, 9]` (which is 99) becomes `[0, 0, 1]` (which is 100).

            """ + LIST_SHAPE + """

            Do not convert to an `int` and back. The whole point of digit chains is
            that they are longer than any integer type — and the carry is the thing
            being tested.
        """,
        fn_name="add_one", params="head", reference=linked_ref(_ref_add_one),
        canonical="""
            def add_one(head):
                dummy = ListNode(0)
                tail = dummy
                carry = 1                     # the +1 IS the initial carry
                node = head
                while node is not None or carry:
                    total = carry + (node.val if node is not None else 0)
                    tail.next = ListNode(total % 10)
                    tail = tail.next
                    carry = total // 10
                    if node is not None:
                        node = node.next
                return dummy.next
        """,
        visible=[("no carry", [[4, 2, 3]]), ("one carry", [[9, 2]])],
        hidden=[("carry all the way", [[9, 9, 9]]), ("zero", [[0]]),
                ("nine", [[9]]), ("longer", [[1, 2, 3, 4, 5]])],
        edges=[("empty", [[]]), ("leading zeros in the number", [[9, 0, 1]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Stopping the loop when the chain ends, losing a final carry",
                  "Treating the carry as a boolean instead of `total // 10`",
                  "Converting the whole chain to an int, which the question exists to "
                  "prevent"],
        nudge="Seed the carry with 1 and the rest is ordinary column addition.",
        visual="Columns from the right; a carry falls into the next column.",
        pseudocode="""
            carry = 1
            while nodes remain or carry:
                total = carry + digit (0 if the chain ended)
                append total % 10; carry = total // 10
        """,
        prerequisites=["ll-number-to-digits"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-add-two", title="The Sum of Two Chains", realm="array_caverns",
        difficulty="MEDIUM", family="linked_arith", pattern="SIMULATION",
        secondary=["TWO_POINTER"], viz=VIZ_CHAIN, profile_weight=Q,
        result_adapter="linked", **pair,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Add Two Numbers is one of the most frequently reported linked-list "
                   "screens.",
        statement="""
            `a` and `b` each hold the digits of a non-negative number in reverse, ones
            column first, and each has at least one digit. Return the digit chain of
            their sum, in the same reverse order.

            `[2, 4, 3] + [5, 6, 4]` is `342 + 465 = 807`, so the answer is `[7, 0, 8]`.

            `a` and `b` are `ListNode` heads.

            The two chains may be different lengths, and the sum may be longer than
            both. One loop handles all three of those if you let a finished chain
            contribute a zero and keep looping while there is still a carry.
        """,
        fn_name="add_two_numbers", params="a, b",
        reference=linked_ref(_ref_add_two, heads=2),
        canonical="""
            def add_two_numbers(a, b):
                dummy = ListNode(0)
                tail = dummy
                carry = 0
                while a is not None or b is not None or carry:
                    total = carry
                    if a is not None:
                        total += a.val
                        a = a.next
                    if b is not None:
                        total += b.val
                        b = b.next
                    tail.next = ListNode(total % 10)
                    tail = tail.next
                    carry = total // 10
                return dummy.next
        """,
        visible=[("classic", [[2, 4, 3], [5, 6, 4]]), ("carry out", [[9, 9], [1]])],
        hidden=[("different lengths", [[1, 2, 3, 4], [9]]),
                ("both zero", [[0], [0]]),
                ("all nines", [[9, 9, 9], [9, 9, 9]]),
                ("no carries", [[1, 1], [2, 2]]),
                ("b is longer", [[5], [5, 5, 5]])],
        edges=[("single digits carrying", [[5], [5]]),
               ("zero plus something", [[0], [1, 2]])],
        constraints=["each chain holds at least one digit", "digits are 0-9"],
        time_complexity="O(max(n, m))", space_complexity="O(max(n, m))",
        failures=["Ending the loop when both chains end, dropping the final carry",
                  "Two separate loops for the leftover tail, which duplicates the "
                  "carry logic and usually gets it wrong once",
                  "Converting both chains to ints — correct for small inputs, and "
                  "exactly what the question is designed to rule out"],
        nudge="`while a or b or carry` is the whole answer to 'what about the leftover "
              "digits?'",
        visual="Long addition, one column per round, carry falling to the right.",
        pseudocode="""
            carry = 0
            while a or b or carry:
                total = carry + a's digit (if any) + b's digit (if any)
                append total % 10; carry = total // 10
        """,
        prerequisites=["ll-add-one"], tags=["core", "linked-list", "classic"],
    ))

    # == SYMMETRY ============================================================

    P.append(rune(
        id="ll-palindrome-guided", title="The Rune That Reads Both Ways",
        realm="twin_pointer_pass", difficulty="GUIDED", family="palindrome",
        pattern="TWO_POINTER", scaffold_for="LINKED LIST: reading a chain backwards",
        cmp="bool", **chain,
        statement="""
            Return `True` if the chain's values read the same forwards and backwards.

            """ + LIST_SHAPE + """

            A chain cannot be read backwards — that is the entire problem. The first
            solution anyone should offer is therefore to copy the values somewhere
            that *can* be read backwards, and say out loud that it costs O(n) memory.

            Two runes are missing: what to record, and the comparison that ends it.
        """,
        fn_name="is_palindrome", params="head",
        reference=linked_ref(_ref_is_palindrome),
        canonical="""
            def is_palindrome(head):
                values = []
                node = head
                while node is not None:
                    values.append(node.val)
                    node = node.next
                return values == values[::-1]
        """,
        blanks=[("values.append(node.val)", "record this node's value in order"),
                ("values == values[::-1]",
                 "the recorded values read the same in both directions")],
        visible=[("odd palindrome", [[1, 2, 1]]), ("not a palindrome", [[1, 2, 3]])],
        hidden=[("even palindrome", [[1, 2, 2, 1]]), ("all identical", [[4, 4, 4]]),
                ("off by one at the end", [[1, 2, 2, 3]]),
                ("negatives", [[-1, 0, -1]])],
        edges=[("empty", [[]]), ("single", [[9]])],
        failures=["Comparing the list to `reversed(values)`, which is an iterator and "
                  "never equal to a list",
                  "Reversing in place with `.reverse()` and then comparing it to itself"],
        nudge="Get the values out of the chain first. Once they are in a Python list, "
              "the question is trivial.",
        visual="Copy the chain into a list, then read it from both ends at once.",
        pseudocode="""
            collect every value in order
            compare the collected values to their own reverse
        """,
        time_complexity="O(n)", space_complexity="O(n)",
        prerequisites=["ll-walk-guided"], tags=["core", "linked-list"],
    ))

    P.append(code_problem(
        id="ll-palindrome", title="The Mirror Chain", realm="twin_pointer_pass",
        difficulty="TUTORIAL", family="palindrome", pattern="TWO_POINTER",
        cmp="bool", viz=VIZ_POINTERS, profile_weight=Q, **chain,
        statement="""
            Return `True` if the chain reads the same in both directions.

            """ + LIST_SHAPE + """

            Write the copy-the-values version from a blank screen, then state its
            memory cost. Interviewers rarely want you to leap straight to the clever
            one; they want the working one, priced honestly, and then the improvement.
        """,
        fn_name="is_palindrome", params="head",
        reference=linked_ref(_ref_is_palindrome),
        canonical="""
            def is_palindrome(head):
                values = []
                node = head
                while node is not None:
                    values.append(node.val)
                    node = node.next
                left, right = 0, len(values) - 1
                while left < right:
                    if values[left] != values[right]:
                        return False
                    left += 1
                    right -= 1
                return True
        """,
        visible=[("palindrome", [[1, 2, 2, 1]]), ("not one", [[1, 2]])],
        hidden=[("odd length", [[1, 2, 3, 2, 1]]), ("all identical", [[7, 7]]),
                ("nearly", [[1, 2, 3, 3, 2, 2]]), ("negatives", [[-5, 4, -5]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Comparing only half the values and forgetting the middle on odd "
                  "lengths — harmless here, but a common off-by-one",
                  "Mutating the chain while reading it"],
        nudge="Two indices converging on the middle of the copied values.",
        visual="Two fingers walking toward each other over the copied values.",
        pseudocode="""
            copy the values out
            left = 0, right = last
            while left < right: mismatch -> False; else step both inward
        """,
        alternates=[{"name": "reverse the second half in place and compare",
                     "note": "O(1) memory. That is the next encounter.",
                     "complexity": "O(n) time, O(1) space"}],
        prerequisites=["ll-palindrome-guided"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-second-half", title="From the Halfway Stone Onward",
        realm="twin_pointer_pass", difficulty="EASY", family="palindrome",
        pattern="TWO_POINTER", viz=VIZ_POINTERS, profile_weight=Q, **chain,
        statement="""
            Return the values from the middle node to the end, as an ordinary Python
            list. For an even-length chain the middle is the second of the two, so
            `[1, 2, 3, 4]` gives `[3, 4]` and `[1, 2, 3]` gives `[2, 3]`.

            """ + LIST_SHAPE + """

            This is `middle_value` that keeps walking instead of stopping, and it is
            the half of the O(1)-memory palindrome check that people get wrong. Get it
            solid here, where nothing else is happening.
        """,
        fn_name="second_half_values", params="head",
        reference=linked_ref(_ref_second_half),
        canonical="""
            def second_half_values(head):
                slow = head
                fast = head
                while fast is not None and fast.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                out = []
                while slow is not None:      # slow is already standing on the middle
                    out.append(slow.val)
                    slow = slow.next
                return out
        """,
        visible=[("even", [[1, 2, 3, 4]]), ("odd", [[1, 2, 3]])],
        hidden=[("two", [[1, 2]]), ("six", [[1, 2, 3, 4, 5, 6]]),
                ("repeats", [[5, 5, 5]]), ("longer", [list(range(9))])],
        edges=[("empty", [[]]), ("single", [[8]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Returning the first half",
                  "Off by one on even lengths — the middle is the second of the two",
                  "Stopping at the middle instead of walking to the end"],
        nudge="Find the middle the way you already know, then keep going.",
        visual="Fast falls off the end; slow carries on from where it stopped.",
        pseudocode="""
            fast/slow until fast can no longer move twice
            collect from slow to the end
        """,
        prerequisites=["ll-middle"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-palindrome-inplace", title="The Mirror, Without a Copy",
        realm="twin_pointer_pass", difficulty="MEDIUM", family="palindrome",
        pattern="TWO_POINTER", secondary=["SIMULATION"], cmp="bool",
        viz=VIZ_POINTERS, profile_weight=Q, **chain,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="The O(1)-space palindrome follow-up is a repeatedly reported "
                   "escalation of the basic version.",
        statement="""
            Return `True` if the chain reads the same in both directions, using O(1)
            extra memory. You may rearrange the chain while you work.

            """ + LIST_SHAPE + """

            Three things you have already built, in sequence: find the middle with
            fast and slow, reverse the second half in place, then walk the two halves
            toward each other. Nothing here is new — the difficulty is entirely in
            splitting cleanly and not walking off the seam.
        """,
        fn_name="is_palindrome_inplace", params="head",
        reference=linked_ref(_ref_is_palindrome),
        canonical="""
            def is_palindrome_inplace(head):
                if head is None or head.next is None:
                    return True
                slow = head
                fast = head
                while fast.next is not None and fast.next.next is not None:
                    slow = slow.next          # slow ends on the LAST node of half one
                    fast = fast.next.next
                second = slow.next
                slow.next = None              # cut the chain in two

                prev = None                   # reverse the second half
                node = second
                while node is not None:
                    following = node.next
                    node.next = prev
                    prev = node
                    node = following

                left, right = head, prev      # the shorter half governs the walk
                while right is not None:
                    if left.val != right.val:
                        return False
                    left = left.next
                    right = right.next
                return True
        """,
        visible=[("even palindrome", [[1, 2, 2, 1]]), ("odd palindrome", [[1, 2, 3, 2, 1]])],
        hidden=[("not a palindrome", [[1, 2, 3]]), ("two different", [[1, 2]]),
                ("two the same", [[6, 6]]), ("all identical", [[4, 4, 4, 4]]),
                ("fails at the seam", [[1, 2, 3, 4, 2, 1]])],
        edges=[("empty", [[]]), ("single", [[5]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Driving the comparison off the first half, which on odd lengths "
                  "runs one node too far",
                  "Forgetting to cut the first half loose, so the walk never terminates",
                  "Stopping the fast/slow loop one node early and splitting in the "
                  "wrong place"],
        nudge="Let the reversed half decide when to stop. It is never longer than the "
              "first half, so it can never run off the end.",
        visual="Cut in the middle, flip the back half, zip the two together.",
        pseudocode="""
            find the end of the first half with fast/slow
            cut; reverse the second half
            walk both halves together while the reversed half lasts
        """,
        prerequisites=["ll-palindrome", "ll-reverse", "ll-second-half"],
        tags=["core", "two-pointer", "classic"],
    ))

    P.append(code_problem(
        id="ll-reorder", title="The Folded Road", realm="twin_pointer_pass",
        difficulty="HARD", family="palindrome", pattern="TWO_POINTER",
        secondary=["SIMULATION"], viz=VIZ_POINTERS, profile_weight=Q,
        result_adapter="linked", boss=True, **chain,
        statement="""
            Reorder the chain in place so it reads first, last, second, second-to-last,
            and so on. Return the head.

            `[1, 2, 3, 4]` becomes `[1, 4, 2, 3]`; `[1, 2, 3, 4, 5]` becomes
            `[1, 5, 2, 4, 3]`.

            """ + LIST_SHAPE + """

            No new nodes, and no Python list of the values. This is three techniques
            welded together — find the middle, reverse the second half, weave the two
            halves — and it is worth doing precisely because you have already written
            all three separately.
        """,
        fn_name="reorder", params="head", reference=linked_ref(_ref_reorder),
        canonical="""
            def reorder(head):
                if head is None or head.next is None:
                    return head

                slow = head                     # 1. end of the first half
                fast = head
                while fast.next is not None and fast.next.next is not None:
                    slow = slow.next
                    fast = fast.next.next
                second = slow.next
                slow.next = None

                prev = None                     # 2. reverse the second half
                while second is not None:
                    following = second.next
                    second.next = prev
                    prev = second
                    second = following

                first, second = head, prev      # 3. weave them together
                while second is not None:
                    first_next = first.next
                    second_next = second.next
                    first.next = second
                    second.next = first_next
                    first = first_next
                    second = second_next
                return head
        """,
        visible=[("even", [[1, 2, 3, 4]]), ("odd", [[1, 2, 3, 4, 5]])],
        hidden=[("six", [[1, 2, 3, 4, 5, 6]]), ("three", [[1, 2, 3]]),
                ("two", [[1, 2]]), ("repeats", [[7, 7, 7, 7]]),
                ("longer", [list(range(9))])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Not cutting the first half loose, which welds a cycle into the "
                  "result",
                  "Saving only one of the two `next` pointers before rewiring",
                  "Weaving while the wrong half is the one still supplying nodes"],
        nudge="Do it in three separate passes with three separate names. Trying to do "
              "it in one is how this becomes unsolvable at a whiteboard.",
        visual="Fold the chain in half and interleave the two layers.",
        pseudocode="""
            split at the middle
            reverse the second half
            while the second half has nodes:
                save both next pointers, cross-link, advance both
        """,
        prerequisites=["ll-palindrome-inplace"],
        tags=["core", "two-pointer", "classic", "boss"],
    ))

    # == TWO CHAINS THAT MEET ================================================

    P.append(rune(
        id="ll-intersect-guided", title="The Rune of the Shared Road",
        realm="twin_pointer_pass", difficulty="GUIDED", family="linked_intersect",
        pattern="TWO_POINTER", scaffold_for="TWO POINTER: walking two chains at once",
        **pair,
        statement="""
            `a` and `b` have the **same length** and share a common tail: from some
            position onward their values are identical all the way to the end. Return
            the first value of that shared tail, or `None` if they never agree.

            `a` and `b` are `ListNode` heads.

            Equal lengths make this easy: walk both chains in step, and the first time
            they agree you are standing at the join. Two runes are missing.
        """,
        fn_name="shared_tail_value", params="a, b",
        reference=linked_ref(_ref_shared_tail, heads=2),
        canonical="""
            def shared_tail_value(a, b):
                while a is not None and b is not None:
                    if a.val == b.val:
                        return a.val
                    a = a.next
                    b = b.next
                return None
        """,
        blanks=[("a.val == b.val", "the two chains have converged here"),
                ("b = b.next", "the second walker must step too, or they fall out of step")],
        visible=[("joins in the middle", [[1, 9, 2, 4], [3, 7, 2, 4]]),
                 ("never joins", [[1, 2, 3], [4, 5, 6]])],
        hidden=[("identical", [[1, 2, 3], [1, 2, 3]]),
                ("joins at the last node", [[1, 2, 9], [3, 4, 9]]),
                ("joins at the second node", [[1, 5, 6], [2, 5, 6]])],
        edges=[("both empty", [[], []]), ("single, shared", [[5], [5]])],
        constraints=["both chains have the same length",
                     "once the chains agree at a position they agree to the end"],
        failures=["Advancing only one of the two cursors",
                  "Comparing `a is b`, which cannot be true for separately built chains",
                  "Returning the last common value instead of the first"],
        nudge="Same length means position `i` in one chain lines up with position `i` "
              "in the other. That is what makes this version trivial.",
        visual="Two roads running side by side until they merge.",
        pseudocode="""
            while both chains have nodes:
                values equal -> that is the join
                otherwise step both
            -> None
        """,
        time_complexity="O(n)", space_complexity="O(1)",
        prerequisites=["ll-walk-guided"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-intersect-equal", title="Two Roads, One Length",
        realm="twin_pointer_pass", difficulty="TUTORIAL", family="linked_intersect",
        pattern="TWO_POINTER", viz=VIZ_POINTERS, profile_weight=Q, **pair,
        statement="""
            `a` and `b` are the same length and share a common tail: from some position
            onward their values agree all the way to the end. Return the first value of
            that shared tail, or `None`.

            `a` and `b` are `ListNode` heads; either may be `None`.

            Write it from scratch. It is four lines, and the reason it is four lines is
            the equal-length guarantee — which the next encounter takes away.
        """,
        fn_name="shared_tail_value", params="a, b",
        reference=linked_ref(_ref_shared_tail, heads=2),
        canonical="""
            def shared_tail_value(a, b):
                while a is not None and b is not None:
                    if a.val == b.val:
                        return a.val
                    a = a.next
                    b = b.next
                return None
        """,
        visible=[("joins late", [[1, 2, 8, 9], [3, 4, 8, 9]]),
                 ("no join", [[1, 2], [3, 4]])],
        hidden=[("joins at the head", [[5, 6, 7], [5, 6, 7]]),
                ("joins at the tail", [[1, 2, 3], [7, 8, 3]]),
                ("single node shared", [[4], [4]]),
                ("single node, no join", [[4], [5]])],
        edges=[("both empty", [[], []]), ("one empty", [[], [1]])],
        constraints=["both chains have the same length",
                     "once the chains agree at a position they agree to the end"],
        time_complexity="O(n)", space_complexity="O(1)",
        failures=["Nested loops over both chains, which is O(n^2) for no reason",
                  "Forgetting the None result when they never meet"],
        nudge="Lockstep. One `while`, two advances, one comparison.",
        visual="Two parallel roads; the first place they touch is the answer.",
        pseudocode="walk both together; first agreement wins; otherwise None",
        prerequisites=["ll-intersect-guided"], tags=["core", "two-pointer"],
    ))

    P.append(code_problem(
        id="ll-intersect", title="Where the Roads Converge",
        realm="twin_pointer_pass", difficulty="EASY", family="linked_intersect",
        pattern="TWO_POINTER", viz=VIZ_POINTERS, profile_weight=Q, **pair,
        source_type="GENERAL_INTERVIEW", year="reported pattern",
        provenance="Finding where two lists converge is a repeatedly reported "
                   "linked-list archetype.",
        statement="""
            `a` and `b` may be **different lengths**. They share a common tail: from
            some position onward their values agree all the way to the end. Return the
            first value of that shared tail, or `None` if they never agree.

            `a` and `b` are `ListNode` heads; either may be `None`.

            Lockstep no longer works, because position 2 of a four-node chain and
            position 2 of a six-node chain are not the same distance from the end.
            Measure both lengths, burn off the difference on the longer one, and the
            problem you already solved reappears.
        """,
        fn_name="shared_tail_value", params="a, b",
        reference=linked_ref(_ref_shared_tail, heads=2),
        canonical="""
            def shared_tail_value(a, b):
                def length(node):
                    total = 0
                    while node is not None:
                        total += 1
                        node = node.next
                    return total

                la, lb = length(a), length(b)
                while la > lb:                 # start them the same distance from the end
                    a = a.next
                    la -= 1
                while lb > la:
                    b = b.next
                    lb -= 1
                while a is not None and b is not None:
                    if a.val == b.val:
                        return a.val
                    a = a.next
                    b = b.next
                return None
        """,
        visible=[("a is longer", [[1, 2, 3, 4, 5], [9, 4, 5]]),
                 ("no shared tail", [[1, 2], [3, 4, 5, 6]])],
        hidden=[("b is longer", [[8, 9], [1, 2, 3, 8, 9]]),
                ("equal lengths", [[1, 2, 7], [3, 4, 7]]),
                ("one is a suffix of the other", [[4, 5, 6], [5, 6]]),
                ("shares everything", [[1, 2, 3], [1, 2, 3]])],
        edges=[("one empty", [[1, 2], []]), ("both empty", [[], []])],
        constraints=["once the chains agree at the same distance from the end, they "
                     "agree all the way to the end"],
        time_complexity="O(n + m)", space_complexity="O(1)",
        failures=["Comparing from the heads without aligning first",
                  "Aligning the wrong chain",
                  "Walking one chain fully for each node of the other, which is O(n·m)"],
        nudge="You cannot walk backwards from the ends, so make the two walkers "
              "equidistant from the ends before you start.",
        visual="Two roads of different lengths, lined up by their far ends.",
        pseudocode="""
            measure both lengths
            advance the longer chain by the difference
            walk both together; first agreement is the join
        """,
        alternates=[{"name": "swap chains at the end so both walk n + m nodes",
                     "note": "No length pass at all, and the version interviewers "
                             "usually have in mind.",
                     "complexity": "O(n + m) time, O(1) space"}],
        prerequisites=["ll-intersect-equal"], tags=["core", "two-pointer", "classic"],
    ))

    # == LINKS THAT POINT BOTH WAYS ==========================================

    dll = dict(preamble=DLL_PREAMBLE, arg_adapters=[], starter_hint=DLL_HINT,
               realm="stack_queue_mines")

    P.append(rune(
        id="dll-guided", title="The Rune of the Backward Link",
        difficulty="GUIDED", family="linked_doubly", pattern="SIMULATION",
        scaffold_for="DOUBLY LINKED LIST: the second pointer", **dll,
        statement="""
            Build a doubly linked list from `values`, then return the values read from
            the **tail backwards**.

            """ + DLL_SHAPE + """

            ```python
            class DListNode:
                def __init__(self, val=0, prev=None, next=None):
                    self.val = val
                    self.prev = prev
                    self.next = next
            ```

            A second pointer is the entire difference, and it buys exactly one thing:
            you can walk backwards, and you can delete a node you are standing on
            without having found its predecessor first. It costs you the discipline of
            keeping both directions consistent at all times.

            The two struck runes are the backward link and the backward walk.
        """,
        fn_name="read_backward", params="values", reference=_ref_read_backward,
        canonical="""
            def read_backward(values):
                head = None
                tail = None
                for value in values:
                    node = DListNode(value)
                    if head is None:
                        head = node
                    else:
                        tail.next = node
                        node.prev = tail
                    tail = node
                out = []
                while tail is not None:
                    out.append(tail.val)
                    tail = tail.prev
                return out
        """,
        blanks=[("node.prev = tail", "the new node also points back at the old tail"),
                ("tail = tail.prev", "walk backwards, which is what the second pointer "
                                     "is for")],
        visible=[("three", [[1, 2, 3]]), ("one", [[5]])],
        hidden=[("repeats", [[4, 4, 4]]), ("negatives", [[-1, -2, -3]]),
                ("longer", [list(range(6))])],
        edges=[("empty", [[]])],
        failures=["Setting `.next` but not `.prev`, so the backward walk stops early",
                  "Walking backwards with `.next`"],
        nudge="Every link you make has two halves. Make both, every time.",
        visual="Each node holds the hand of the one in front and the one behind.",
        pseudocode="""
            build forwards, wiring next AND prev
            from the tail, follow prev to the head, collecting values
        """,
        time_complexity="O(n)", space_complexity="O(n)",
        tags=["core", "linked-list", "doubly"],
    ))

    P.append(code_problem(
        id="dll-backward", title="The Chain That Reads Both Ways",
        difficulty="TUTORIAL", family="linked_doubly", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, **dll,
        statement="""
            Build a doubly linked list from `values` and return the values read from
            the tail backwards, as an ordinary Python list.

            """ + DLL_SHAPE + """

            Write the whole thing. Keeping `.prev` correct while you build is the
            habit the rest of this section depends on.
        """,
        fn_name="read_backward", params="values", reference=_ref_read_backward,
        canonical="""
            def read_backward(values):
                head = None
                tail = None
                for value in values:
                    node = DListNode(value)
                    if head is None:
                        head = node          # the first node is both head and tail
                    else:
                        tail.next = node     # forward link
                        node.prev = tail     # and the matching backward link
                    tail = node
                out = []
                while tail is not None:
                    out.append(tail.val)
                    tail = tail.prev
                return out
        """,
        visible=[("four", [[1, 2, 3, 4]]), ("two", [[8, 9]])],
        hidden=[("single", [[3]]), ("repeats", [[2, 2]]),
                ("negatives", [[-5, 0, 5]]), ("longer", [list(range(7))])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Losing the tail, so there is nowhere to start walking back from",
                  "Wiring `.prev` to the new node instead of the old tail"],
        nudge="Track head and tail as you build. You need the tail to start the walk "
              "back.",
        visual="Two arrows between every neighbouring pair.",
        pseudocode="""
            for each value: make a node, link it after the tail both ways, move tail
            then follow prev from the tail, collecting values
        """,
        prerequisites=["dll-guided"], tags=["core", "doubly"],
    ))

    P.append(code_problem(
        id="dll-remove", title="Pulling a Link Out of the Middle",
        difficulty="EASY", family="linked_doubly", pattern="SIMULATION",
        viz=VIZ_CHAIN, profile_weight=Q, **dll,
        statement="""
            Build a doubly linked list from `values`, remove the **first** node whose
            value equals `target` (if there is one), and return `[forward, backward]` —
            the remaining values read from the head forwards, and from the tail
            backwards.

            """ + DLL_SHAPE + """

            Both directions are returned because both directions are what you get
            wrong. A removal in a doubly linked list touches two links, and if you fix
            only the forward one the list still looks correct from the head and is
            broken from the tail. Removing the head or the tail also moves those, which
            is the other half of the exercise.
        """,
        fn_name="dll_remove", params="values, target", reference=_ref_dll_remove,
        canonical="""
            def dll_remove(values, target):
                head = None
                tail = None
                for value in values:
                    node = DListNode(value)
                    if head is None:
                        head = node
                    else:
                        tail.next = node
                        node.prev = tail
                    tail = node

                node = head
                while node is not None and node.val != target:
                    node = node.next
                if node is not None:
                    if node.prev is not None:
                        node.prev.next = node.next
                    else:
                        head = node.next        # removed the head
                    if node.next is not None:
                        node.next.prev = node.prev
                    else:
                        tail = node.prev        # removed the tail

                forward, walk = [], head
                while walk is not None:
                    forward.append(walk.val)
                    walk = walk.next
                backward, walk = [], tail
                while walk is not None:
                    backward.append(walk.val)
                    walk = walk.prev
                return [forward, backward]
        """,
        visible=[("middle", [[1, 2, 3], 2]), ("absent", [[1, 2, 3], 9])],
        hidden=[("head", [[1, 2, 3], 1]), ("tail", [[1, 2, 3], 3]),
                ("only node", [[7], 7]), ("first of two equal", [[4, 4], 4]),
                ("negatives", [[-1, -2, -3], -2])],
        edges=[("empty", [[], 1]), ("single, absent", [[5], 1])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Fixing `.next` but not `.prev`, which the backward read exposes",
                  "Dereferencing `node.prev.next` when the node is the head",
                  "Forgetting to move `tail` when the removed node was the tail"],
        nudge="Four cases, and they are all the same two lines guarded by 'is there "
              "anything on that side?'",
        visual="Two neighbours reach past the departing node and take each other's hand.",
        pseudocode="""
            build the doubly linked chain
            find the first matching node
            prev exists -> prev.next = node.next  else head = node.next
            next exists -> next.prev = node.prev  else tail = node.prev
            read forwards from head and backwards from tail
        """,
        prerequisites=["dll-backward"], tags=["core", "doubly"],
    ))

    P.append(design_problem(
        id="dll-deque", title="The Two-Mouthed Cart", realm="stack_queue_mines",
        difficulty="MEDIUM", cls_name="Deque", reference_cls=RefDeque,
        family="linked_doubly", secondary=["QUEUE", "STACK"], profile_weight=Q,
        statement="""
            Build a `Deque` on top of your own doubly linked list — no Python `list`,
            no `collections.deque` — supporting all of these in O(1):

            - `push_front(value)` and `push_back(value)`, both returning `None`
            - `pop_front()` and `pop_back()`, returning the removed value, or `None`
              when empty
            - `to_list()`, the values from front to back
            - `size()`, the number of values held

            A Python list would make `push_front` O(n), which is the entire reason
            this structure exists. Define your own node class with `.prev` and `.next`.

            Two sentinel nodes — a permanent head and a permanent tail that never hold
            data — remove every "is the list empty?" branch from the insert and remove
            paths. That trick is worth learning here, because the next encounter is
            unpleasant without it.
        """,
        canonical="""
            class _DNode:
                def __init__(self, val=None):
                    self.val = val
                    self.prev = None
                    self.next = None


            class Deque:
                def __init__(self):
                    self.head = _DNode()          # sentinels: never removed, never read
                    self.tail = _DNode()
                    self.head.next = self.tail
                    self.tail.prev = self.head
                    self.count = 0

                def _insert_after(self, anchor, node):
                    node.prev = anchor
                    node.next = anchor.next
                    anchor.next.prev = node
                    anchor.next = node
                    self.count += 1

                def _unlink(self, node):
                    node.prev.next = node.next
                    node.next.prev = node.prev
                    self.count -= 1
                    return node.val

                def push_front(self, value):
                    self._insert_after(self.head, _DNode(value))
                    return None

                def push_back(self, value):
                    self._insert_after(self.tail.prev, _DNode(value))
                    return None

                def pop_front(self):
                    if self.count == 0:
                        return None
                    return self._unlink(self.head.next)

                def pop_back(self):
                    if self.count == 0:
                        return None
                    return self._unlink(self.tail.prev)

                def to_list(self):
                    out = []
                    node = self.head.next
                    while node is not self.tail:
                        out.append(node.val)
                        node = node.next
                    return out

                def size(self):
                    return self.count
        """,
        visible=[
            ("both ends",
             ["__init__", "push_back", "push_front", "to_list", "size"],
             [[], [2], [1], [], []]),
            ("pop from the front",
             ["__init__", "push_back", "push_back", "pop_front", "to_list"],
             [[], [1], [2], [], []]),
        ],
        hidden=[
            ("pop from the back",
             ["__init__", "push_front", "push_front", "pop_back", "to_list"],
             [[], [1], [2], [], []]),
            ("drain completely",
             ["__init__", "push_back", "pop_front", "pop_front", "size"],
             [[], [5], [], [], []]),
            ("interleaved",
             ["__init__", "push_front", "push_back", "push_front", "to_list", "size"],
             [[], [2], [3], [1], [], []]),
            ("refill after draining",
             ["__init__", "push_back", "pop_back", "push_back", "to_list"],
             [[], [1], [], [2], []]),
        ],
        edges=[
            ("empty pops",
             ["__init__", "pop_front", "pop_back", "to_list", "size"],
             [[], [], [], [], []]),
            ("single value from both ends",
             ["__init__", "push_front", "pop_back", "size"], [[], [9], [], []]),
        ],
        time_complexity="O(1)", space_complexity="O(n)",
        failures=["Storing the values in a Python list, which makes push_front O(n)",
                  "Popping from an empty deque and raising instead of returning None",
                  "Leaving a stale `.prev` on a removed node's neighbour",
                  "Forgetting to move both head and tail when the last value leaves"],
        nudge="Put two nodes that never hold data at each end. Then every insert has a "
              "node before it and a node after it, always.",
        visual="A cart with a permanent front wall and a permanent back wall; cargo "
               "lives strictly between them.",
        pseudocode="""
            head <-> tail sentinels
            insert_after(anchor, node): four pointer writes, no branches
            unlink(node): two pointer writes, no branches
            pop on empty -> None
        """,
        tags=["core", "design", "doubly"],
    ))

    # == THE VAULT THAT FORGETS ==============================================

    lru = dict(realm="hashmap_highlands", family="linked_lru",
               starter_hint="keys arrive in order; capacity is how many fit at once")

    P.append(rune(
        id="lru-guided", title="The Rune of the Forgetting Vault",
        difficulty="GUIDED", pattern="SIMULATION",
        scaffold_for="LRU: recency as an order", secondary=["HASH_MAP", "DESIGN"],
        **lru,
        statement="""
            A cache holds at most `capacity` keys. `keys` is the sequence of keys
            requested, in order. Return the keys still in the cache at the end,
            **least recently used first**.

            Two rules, and they are the whole of LRU:

            - touching a key makes it the most recently used
            - when the cache is over capacity, the least recently used key is dropped

            The simulation keeps the keys in a list ordered oldest to newest. Two runes
            are missing, one for each rule.
        """,
        fn_name="lru_order", params="capacity, keys", reference=_ref_lru_order,
        canonical="""
            def lru_order(capacity, keys):
                order = []
                for key in keys:
                    if key in order:
                        order.remove(key)
                    order.append(key)
                    if len(order) > capacity:
                        order.pop(0)
                return order
        """,
        blanks=[("order.remove(key)",
                 "a repeat visit is not a new entry: take it out of its old position"),
                ("order.pop(0)",
                 "over capacity: drop the key at the oldest end")],
        visible=[("no eviction", [3, ["a", "b", "c"]]),
                 ("one eviction", [2, ["a", "b", "c"]])],
        hidden=[("repeat refreshes", [2, ["a", "b", "a", "c"]]),
                ("same key throughout", [2, ["a", "a", "a"]]),
                ("capacity of one", [1, ["a", "b", "c"]]),
                ("longer trace", [3, ["a", "b", "c", "a", "d", "e", "b"]])],
        edges=[("no keys", [2, []]), ("capacity zero", [0, ["a", "b"]])],
        failures=["Appending without removing the old position, so a key appears twice",
                  "Evicting the newest key instead of the oldest",
                  "Evicting before inserting, which keeps one entry too few"],
        nudge="The list IS the recency order. Front is oldest, back is newest, and "
              "every touch moves a key to the back.",
        visual="A queue where a returning customer goes to the back of the line.",
        pseudocode="""
            for each key:
                already present -> pull it out
                append it (now the newest)
                over capacity -> drop the front
        """,
        time_complexity="O(n·c)", space_complexity="O(c)",
        tags=["core", "design", "lru"],
    ))

    P.append(code_problem(
        id="lru-evictions", title="What the Vault Let Go",
        difficulty="TUTORIAL", pattern="SIMULATION", secondary=["HASH_MAP", "DESIGN"],
        viz=VIZ_MAP, profile_weight=Q, **lru,
        statement="""
            Same cache, same two rules. This time return the list of keys that were
            **evicted**, in the order they were evicted.

            A cache holds at most `capacity` keys; `keys` is the request sequence.
            Touching a key refreshes it; going over capacity drops the least recently
            used one.
        """,
        fn_name="lru_evictions", params="capacity, keys", reference=_ref_lru_evictions,
        canonical="""
            def lru_evictions(capacity, keys):
                order = []
                evicted = []
                for key in keys:
                    if key in order:
                        order.remove(key)     # refresh, do not duplicate
                    order.append(key)
                    if len(order) > capacity:
                        evicted.append(order.pop(0))
                return evicted
        """,
        visible=[("two evictions", [2, ["a", "b", "c", "d"]]),
                 ("none", [3, ["a", "b", "c"]])],
        hidden=[("refresh saves a key", [2, ["a", "b", "a", "c"]]),
                ("capacity of one", [1, ["a", "b", "a"]]),
                ("all the same key", [2, ["a", "a", "a"]]),
                ("longer trace", [3, ["a", "b", "c", "a", "d", "e", "b"]])],
        edges=[("no keys", [2, []]), ("capacity zero", [0, ["a"]])],
        time_complexity="O(n·c)", space_complexity="O(c)",
        failures=["Recording the evicted key after removing it from the wrong end",
                  "Counting a refresh as an insertion and evicting too eagerly"],
        nudge="Identical loop to the last one. Only what you record changes.",
        visual="The front of the queue, leaving.",
        pseudocode="""
            same simulation; every time you drop the front, write it down
        """,
        prerequisites=["lru-guided"], tags=["core", "design", "lru"],
    ))

    P.append(code_problem(
        id="lru-hits", title="How Often the Vault Remembered",
        difficulty="EASY", pattern="SIMULATION", secondary=["HASH_MAP", "DESIGN"],
        viz=VIZ_MAP, profile_weight=Q, **lru,
        statement="""
            Same cache, same two rules. Return how many requests were **hits** — that
            is, how many times a requested key was already in the cache.

            A cache holds at most `capacity` keys; `keys` is the request sequence.
            Touching a key refreshes it; going over capacity drops the least recently
            used one.

            This is the number that decides whether a cache was worth having, which is
            why it is the first thing anyone asks about one.
        """,
        fn_name="lru_hits", params="capacity, keys", reference=_ref_lru_hits,
        canonical="""
            def lru_hits(capacity, keys):
                order = []
                hits = 0
                for key in keys:
                    if key in order:
                        hits += 1
                        order.remove(key)
                    order.append(key)
                    if len(order) > capacity:
                        order.pop(0)
                return hits
        """,
        visible=[("one hit", [2, ["a", "b", "a"]]), ("no hits", [2, ["a", "b", "c"]])],
        hidden=[("every repeat hits", [3, ["a", "a", "a"]]),
                ("evicted then requested again", [1, ["a", "b", "a"]]),
                ("refresh keeps it alive", [2, ["a", "b", "a", "c", "a"]]),
                ("longer trace", [3, ["a", "b", "c", "a", "d", "e", "b"]])],
        edges=[("no keys", [2, []]), ("capacity zero", [0, ["a", "a"]])],
        time_complexity="O(n·c)", space_complexity="O(c)",
        failures=["Counting a hit for a key that was evicted earlier in the trace",
                  "Counting the first sighting of a key as a hit",
                  "Refreshing on a miss as well, which is right, and then also counting "
                  "it, which is not"],
        nudge="A hit is a request for a key the cache still holds. Eviction is what "
              "makes that question interesting.",
        visual="Every request either finds the key or pays for it.",
        pseudocode="""
            same simulation; count the requests where the key was already present
        """,
        prerequisites=["lru-evictions"], tags=["core", "design", "lru"],
    ))

    P.append(design_problem(
        id="ll-lru-dll", title="The Vault Built From Links",
        realm="hashmap_highlands", difficulty="HARD", cls_name="LRUCache",
        reference_cls=RefLRUCache, family="linked_lru", secondary=["HASH_MAP"],
        profile_weight=Q, boss=True,
        source_type="GENERAL_INTERVIEW",
        provenance="Hand-rolling an LRU cache from a hash map and a doubly linked "
                   "list is one of the most frequently reported design screens.",
        statement="""
            Build an `LRUCache` with `__init__(capacity)`, `get(key)` and
            `put(key, value)`, every one of them O(1). `get` returns the value, or `-1`
            if the key is absent. `put` returns `None`. Also provide `keys()`,
            returning the keys held, **most recently used first**, so your ordering can
            be inspected.

            `collections.OrderedDict` is banned here. The point of this encounter is
            the structure underneath it: a dict from key to node, plus a doubly linked
            list holding recency order.

            Why both: the dict gives you O(1) lookup but no order, and the list gives
            you O(1) reordering but no lookup. Neither is enough alone. The dict finds
            the node; the node's own `.prev` and `.next` let you unlink it without
            searching for it.

            Use two sentinel nodes. Without them, `put` on an empty cache, `get` on the
            most recent key and eviction of the last remaining key are three separate
            special cases, and one of them will be wrong.
        """,
        canonical="""
            class _LNode:
                def __init__(self, key=None, value=None):
                    self.key = key          # the node remembers its key, so eviction
                    self.value = value      # can delete the right dict entry
                    self.prev = None
                    self.next = None


            class LRUCache:
                def __init__(self, capacity):
                    self.capacity = capacity
                    self.table = {}         # key -> node
                    self.head = _LNode()    # sentinel: most recently used side
                    self.tail = _LNode()    # sentinel: least recently used side
                    self.head.next = self.tail
                    self.tail.prev = self.head

                def _unlink(self, node):
                    node.prev.next = node.next
                    node.next.prev = node.prev

                def _push_front(self, node):
                    node.prev = self.head
                    node.next = self.head.next
                    self.head.next.prev = node
                    self.head.next = node

                def get(self, key):
                    node = self.table.get(key)
                    if node is None:
                        return -1
                    self._unlink(node)          # O(1) because the dict handed us the
                    self._push_front(node)      # node itself, not a position to search
                    return node.value

                def put(self, key, value):
                    node = self.table.get(key)
                    if node is not None:
                        node.value = value
                        self._unlink(node)
                        self._push_front(node)
                        return None
                    node = _LNode(key, value)
                    self.table[key] = node
                    self._push_front(node)
                    if len(self.table) > self.capacity:
                        victim = self.tail.prev
                        self._unlink(victim)
                        del self.table[victim.key]
                    return None

                def keys(self):
                    out = []
                    node = self.head.next
                    while node is not self.tail:
                        out.append(node.key)
                        node = node.next
                    return out
        """,
        visible=[
            ("hit and miss",
             ["__init__", "put", "put", "get", "get"],
             [[2], ["a", 1], ["b", 2], ["a"], ["z"]]),
            ("eviction",
             ["__init__", "put", "put", "put", "get", "keys"],
             [[2], ["a", 1], ["b", 2], ["c", 3], ["a"], []]),
        ],
        hidden=[
            ("get refreshes recency",
             ["__init__", "put", "put", "get", "put", "get", "get"],
             [[2], ["a", 1], ["b", 2], ["a"], ["c", 3], ["b"], ["a"]]),
            ("overwrite does not grow the cache",
             ["__init__", "put", "put", "keys", "get"],
             [[2], ["a", 1], ["a", 9], [], ["a"]]),
            ("capacity of one",
             ["__init__", "put", "put", "get", "get"],
             [[1], ["a", 1], ["b", 2], ["a"], ["b"]]),
            ("order after several touches",
             ["__init__", "put", "put", "put", "get", "keys"],
             [[3], ["a", 1], ["b", 2], ["c", 3], ["a"], []]),
            ("evicted key returns as a miss",
             ["__init__", "put", "put", "put", "get", "put", "get"],
             [[2], ["a", 1], ["b", 2], ["c", 3], ["a"], ["a", 7], ["a"]]),
        ],
        edges=[
            ("get on an empty cache", ["__init__", "get", "keys"], [[2], ["a"], []]),
            ("capacity of one, repeated put",
             ["__init__", "put", "put", "keys", "get"],
             [[1], ["a", 1], ["a", 2], [], ["a"]]),
        ],
        time_complexity="O(1)", space_complexity="O(capacity)",
        failures=["Storing the value in the dict and the key in the list, then having "
                  "to search the list to reorder it — that is O(n), and it is the "
                  "mistake this problem exists to catch",
                  "Not storing the key on the node, so eviction cannot find the dict "
                  "entry to delete",
                  "Refreshing on `put` of an existing key but not on `get`",
                  "Evicting before inserting, or checking capacity against the list "
                  "length after it has drifted from the dict"],
        nudge="The dict does not map key to value. It maps key to the NODE that holds "
              "the value, and that is what makes the reordering O(1).",
        visual="A ledger pointing into a chain: look up in the ledger, unhook in the "
               "chain, re-hang at the front.",
        pseudocode="""
            table: key -> node ; head <-> tail sentinels, most recent at the front
            get:  node = table[key] or -1 ; unlink ; push_front ; return value
            put:  existing -> update, unlink, push_front
                  new      -> node, table[key] = node, push_front
                              over capacity -> victim = tail.prev; unlink; del table[key]
        """,
        tags=["core", "design", "lru", "classic", "boss"],
    ))

    return P
