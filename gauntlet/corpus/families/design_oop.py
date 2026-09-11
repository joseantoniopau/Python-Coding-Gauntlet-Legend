"""Stateful design encounters — the 'build me a thing that remembers' interview."""
from __future__ import annotations

from collections import OrderedDict, defaultdict, deque

from ._base import design_problem

Q = {"PRACTICAL": 3.0, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.5}
QS = {"PRACTICAL": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}


class RefTextEditor:
    def __init__(self):
        self.text = ""
        self.clipboard = ""
        self.history = []

    def append(self, chunk):
        self.history.append(self.text)
        self.text += chunk
        return self.text

    def delete(self, count):
        self.history.append(self.text)
        removed = self.text[-count:] if count > 0 else ""
        self.text = self.text[:-count] if count > 0 else self.text
        return removed

    def copy(self, start, end):
        self.clipboard = self.text[start:end]
        return self.clipboard

    def paste(self, times):
        self.history.append(self.text)
        self.text += self.clipboard * times
        return self.text

    def undo(self):
        if self.history:
            self.text = self.history.pop()
        return self.text

    def value(self):
        return self.text


class RefMinStack:
    def __init__(self):
        self.stack = []
        self.mins = []

    def push(self, value):
        self.stack.append(value)
        self.mins.append(value if not self.mins else min(value, self.mins[-1]))
        return None

    def pop(self):
        if not self.stack:
            return None
        self.mins.pop()
        return self.stack.pop()

    def top(self):
        return self.stack[-1] if self.stack else None

    def get_min(self):
        return self.mins[-1] if self.mins else None


class RefLRUCache:
    def __init__(self, capacity=2):
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
        return list(self.store)


class RefHashMap:
    def __init__(self, buckets=8):
        self.buckets = [[] for _ in range(buckets)]
        self.size = buckets

    def _slot(self, key):
        return hash(key) % self.size

    def put(self, key, value):
        slot = self.buckets[self._slot(key)]
        for i, (k, _) in enumerate(slot):
            if k == key:
                slot[i] = (key, value)
                return None
        slot.append((key, value))
        return None

    def get(self, key):
        for k, v in self.buckets[self._slot(key)]:
            if k == key:
                return v
        return -1

    def remove(self, key):
        slot = self.buckets[self._slot(key)]
        for i, (k, _) in enumerate(slot):
            if k == key:
                slot.pop(i)
                return True
        return False


class RefRateLimiter:
    def __init__(self, window=10, limit=3):
        self.window = window
        self.limit = limit
        self.hits = defaultdict(deque)

    def allow(self, key, now):
        q = self.hits[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class RefEventLogger:
    def __init__(self, cooldown=10):
        self.cooldown = cooldown
        self.last = {}

    def should_print(self, message, timestamp):
        previous = self.last.get(message)
        if previous is not None and timestamp < previous + self.cooldown:
            return False
        self.last[message] = timestamp
        return True


class RefUndoStack:
    def __init__(self):
        self.done = []
        self.undone = []

    def do(self, action):
        self.done.append(action)
        self.undone.clear()
        return list(self.done)

    def undo(self):
        if not self.done:
            return None
        action = self.done.pop()
        self.undone.append(action)
        return action

    def redo(self):
        if not self.undone:
            return None
        action = self.undone.pop()
        self.done.append(action)
        return action


class RefTimeMap:
    def __init__(self):
        self.store = defaultdict(list)

    def set(self, key, value, timestamp):
        self.store[key].append((timestamp, value))
        return None

    def get(self, key, timestamp):
        import bisect
        entries = self.store.get(key, [])
        i = bisect.bisect_right(entries, (timestamp, chr(0x10FFFF)))
        return entries[i - 1][1] if i else ""


class RefMovingWindow:
    def __init__(self, size=3):
        self.size = size
        self.window = deque()
        self.total = 0

    def add(self, value):
        self.window.append(value)
        self.total += value
        if len(self.window) > self.size:
            self.total -= self.window.popleft()
        return self.total


def build() -> list:
    P: list = []

    P.append(design_problem(
        id="ds-text-editor", title="The Editor Automaton", realm="matrix_citadel",
        difficulty="HARD", cls_name="TextEditor", reference_cls=RefTextEditor,
        profile_weight=Q, boss=True, secondary=["STACK", "SIMULATION"],
        source_type="REPORTED_INTERVIEW",
        provenance="Stateful text-editor simulation is a repeatedly reported archetype.",
        statement="""
            Build a `TextEditor` supporting:

            - `append(chunk)` — add text to the end, return the full text
            - `delete(count)` — remove the last `count` characters, return what was removed
            - `copy(start, end)` — copy the slice `[start:end]` to the clipboard, return it
            - `paste(times)` — append the clipboard `times` times, return the full text
            - `undo()` — revert the last text-changing operation, return the full text
            - `value()` — return the current text

            `copy` does not change the text and is therefore **not** undoable.
            `undo` on a fresh editor is a no-op. `delete(0)` removes nothing.
        """,
        canonical="""
            class TextEditor:
                def __init__(self):
                    self.text = ""
                    self.clipboard = ""
                    self.history = []        # snapshots BEFORE each mutating op

                def append(self, chunk):
                    self.history.append(self.text)
                    self.text += chunk
                    return self.text

                def delete(self, count):
                    self.history.append(self.text)
                    if count <= 0:
                        return ""
                    removed = self.text[-count:]
                    self.text = self.text[:-count]
                    return removed

                def copy(self, start, end):
                    self.clipboard = self.text[start:end]
                    return self.clipboard     # no history push: nothing changed

                def paste(self, times):
                    self.history.append(self.text)
                    self.text += self.clipboard * times
                    return self.text

                def undo(self):
                    if self.history:
                        self.text = self.history.pop()
                    return self.text

                def value(self):
                    return self.text
        """,
        visible=[
            ("append and undo",
             ["__init__", "append", "append", "undo", "value"],
             [[], ["hello"], [" world"], [], []]),
            ("copy and paste",
             ["__init__", "append", "copy", "paste", "value"],
             [[], ["ab"], [0, 2], [2], []]),
        ],
        hidden=[
            ("delete returns removed",
             ["__init__", "append", "delete", "value"], [[], ["abcdef"], [2], []]),
            ("undo after paste",
             ["__init__", "append", "copy", "paste", "undo", "value"],
             [[], ["xy"], [0, 1], [3], [], []]),
            ("copy is not undoable",
             ["__init__", "append", "copy", "undo", "value"],
             [[], ["abc"], [0, 2], [], []]),
            ("multiple undos",
             ["__init__", "append", "append", "append", "undo", "undo", "value"],
             [[], ["a"], ["b"], ["c"], [], [], []]),
        ],
        edges=[
            ("undo on empty editor", ["__init__", "undo", "value"], [[], [], []]),
            ("delete zero", ["__init__", "append", "delete", "value"],
             [[], ["abc"], [0], []]),
            ("paste with empty clipboard",
             ["__init__", "append", "paste", "value"], [[], ["a"], [3], []]),
        ],
        constraints=["Operations are called in sequence on one instance",
                     "`copy` never changes the text"],
        time_complexity="O(len(text)) per snapshot", space_complexity="O(ops · len(text))",
        failures=["Pushing history inside `copy`, so one undo appears to do nothing",
                  "`self.text[:-0]` is the empty string, not the whole string — "
                  "`delete(0)` needs a guard",
                  "Storing a reference rather than a snapshot",
                  "Returning the wrong thing: `delete` returns what was removed, not "
                  "the remaining text"],
        nudge="Undo means 'restore the previous state'. The simplest correct version "
              "snapshots the whole string before every mutating operation.",
        visual="A stack of past texts. Every mutating call pushes; undo pops.",
        pseudocode="""
            mutating op: history.append(text); mutate
            undo:        text = history.pop() if history
            copy:        clipboard = text[start:end]   (no history push)
        """,
        tags=["core", "practical", "design", "boss"],
    ))

    P.append(design_problem(
        id="ds-min-stack", title="The Weighted Cart", realm="stack_queue_mines",
        difficulty="MEDIUM", cls_name="MinStack", reference_cls=RefMinStack,
        profile_weight=Q, secondary=["STACK"],
        statement="""
            Build a `MinStack` with `push(value)`, `pop()`, `top()` and `get_min()`, all
            in O(1). `pop`, `top` and `get_min` return `None` on an empty stack.
            `push` returns `None`.
        """,
        canonical="""
            class MinStack:
                def __init__(self):
                    self.stack = []
                    self.mins = []           # running minimum, one per stack entry

                def push(self, value):
                    self.stack.append(value)
                    self.mins.append(value if not self.mins
                                     else min(value, self.mins[-1]))
                    return None

                def pop(self):
                    if not self.stack:
                        return None
                    self.mins.pop()
                    return self.stack.pop()

                def top(self):
                    return self.stack[-1] if self.stack else None

                def get_min(self):
                    return self.mins[-1] if self.mins else None
        """,
        visible=[
            ("basic", ["__init__", "push", "push", "get_min", "pop", "get_min"],
             [[], [3], [1], [], [], []]),
            ("top", ["__init__", "push", "top"], [[], [5], []]),
        ],
        hidden=[
            ("duplicated minimum",
             ["__init__", "push", "push", "pop", "get_min"], [[], [1], [1], [], []]),
            ("increasing", ["__init__", "push", "push", "get_min"], [[], [1], [9], []]),
            ("negatives", ["__init__", "push", "push", "get_min"], [[], [-1], [-5], []]),
        ],
        edges=[
            ("empty pop", ["__init__", "pop", "get_min", "top"], [[], [], [], []]),
            ("push then pop to empty",
             ["__init__", "push", "pop", "get_min"], [[], [1], [], []]),
        ],
        time_complexity="O(1)", space_complexity="O(n)",
        failures=["Calling min(self.stack) makes get_min O(n)",
                  "Only pushing to the mins stack on a new minimum, then popping it "
                  "unconditionally",
                  "Failing on duplicate minimum values"],
        nudge="Carry the answer alongside the data. Each entry remembers the minimum as "
              "of the moment it was pushed.",
        visual="Two carts running side by side; the second holds the running minimum.",
        pseudocode="mins.append(min(value, mins[-1] if mins else value))",
        tags=["core", "design"],
    ))

    P.append(design_problem(
        id="ds-lru-cache", title="The Forgetting Vault", realm="hashmap_highlands",
        difficulty="HARD", cls_name="LRUCache", reference_cls=RefLRUCache,
        profile_weight=Q, secondary=["HASH_MAP", "QUEUE"],
        statement="""
            Build an `LRUCache(capacity)` with:

            - `get(key)` — return the value, or `-1` if absent. A hit counts as a use.
            - `put(key, value)` — insert or overwrite. A write counts as a use. When the
              cache exceeds capacity, evict the **least recently used** key.
            - `keys()` — return the live keys from least to most recently used.

            Both `get` and `put` must be O(1) on average.
        """,
        canonical="""
            class LRUCache:
                def __init__(self, capacity=2):
                    from collections import OrderedDict
                    self.capacity = capacity
                    self.store = OrderedDict()

                def get(self, key):
                    if key not in self.store:
                        return -1
                    self.store.move_to_end(key)       # mark as most recently used
                    return self.store[key]

                def put(self, key, value):
                    if key in self.store:
                        self.store.move_to_end(key)
                    self.store[key] = value
                    if len(self.store) > self.capacity:
                        self.store.popitem(last=False)  # drop the oldest end
                    return None

                def keys(self):
                    return list(self.store)
        """,
        visible=[
            ("evicts oldest",
             ["__init__", "put", "put", "put", "keys"],
             [[2], ["a", 1], ["b", 2], ["c", 3], []]),
            ("get refreshes",
             ["__init__", "put", "put", "get", "put", "keys"],
             [[2], ["a", 1], ["b", 2], ["a"], ["c", 3], []]),
        ],
        hidden=[
            ("overwrite refreshes",
             ["__init__", "put", "put", "put", "put", "keys"],
             [[2], ["a", 1], ["b", 2], ["a", 9], ["c", 3], []]),
            ("miss returns -1", ["__init__", "get"], [[2], ["nope"]]),
            ("capacity one",
             ["__init__", "put", "put", "get", "keys"],
             [[1], ["a", 1], ["b", 2], ["a"], []]),
        ],
        edges=[
            ("get on empty", ["__init__", "get", "keys"], [[3], ["x"], []]),
            ("repeated put same key",
             ["__init__", "put", "put", "keys"], [[2], ["a", 1], ["a", 2], []]),
        ],
        time_complexity="O(1) average", space_complexity="O(capacity)",
        failures=["Not refreshing on `get`, so a hot key gets evicted",
                  "Not refreshing when overwriting an existing key",
                  "Scanning for the oldest key is O(n)",
                  "`popitem()` defaults to last=True — that evicts the newest"],
        nudge="You need both O(1) lookup and a maintained recency order. `OrderedDict` "
              "gives you exactly that pairing; a dict plus a doubly linked list is the "
              "from-scratch answer.",
        visual="A queue of keys where every touch moves a key to the back. Eviction "
               "always takes the front.",
        pseudocode="""
            get: miss -> -1; hit -> move_to_end, return value
            put: existing -> move_to_end; assign; over capacity -> popitem(last=False)
        """,
        tags=["core", "practical", "design"],
    ))

    P.append(design_problem(
        id="ds-hash-map", title="Forging the Vault Itself", realm="hashmap_highlands",
        difficulty="MEDIUM", cls_name="SimpleHashMap", reference_cls=RefHashMap,
        profile_weight=Q, secondary=["HASH_MAP"],
        statement="""
            Implement a hash map from scratch with separate chaining:

            - `put(key, value)` — insert or overwrite, return `None`
            - `get(key)` — return the value or `-1`
            - `remove(key)` — return `True` if a key was removed, `False` otherwise

            Use a fixed number of buckets (`8`) with a list per bucket. Do not use a
            `dict` for storage.
        """,
        canonical="""
            class SimpleHashMap:
                def __init__(self, buckets=8):
                    self.size = buckets
                    self.buckets = [[] for _ in range(buckets)]

                def _slot(self, key):
                    return hash(key) % self.size

                def put(self, key, value):
                    slot = self.buckets[self._slot(key)]
                    for i, (k, _) in enumerate(slot):
                        if k == key:
                            slot[i] = (key, value)     # overwrite in place
                            return None
                    slot.append((key, value))
                    return None

                def get(self, key):
                    for k, v in self.buckets[self._slot(key)]:
                        if k == key:
                            return v
                    return -1

                def remove(self, key):
                    slot = self.buckets[self._slot(key)]
                    for i, (k, _) in enumerate(slot):
                        if k == key:
                            slot.pop(i)
                            return True
                    return False
        """,
        visible=[
            ("put and get", ["__init__", "put", "get"], [[], ["a", 1], ["a"]]),
            ("missing", ["__init__", "get"], [[], ["nope"]]),
        ],
        hidden=[
            ("overwrite", ["__init__", "put", "put", "get"],
             [[], ["a", 1], ["a", 2], ["a"]]),
            ("remove", ["__init__", "put", "remove", "get"], [[], ["a", 1], ["a"], ["a"]]),
            ("remove missing", ["__init__", "remove"], [[], ["ghost"]]),
            ("many keys", ["__init__", "put", "put", "put", "get", "get"],
             [[], ["a", 1], ["b", 2], ["c", 3], ["b"], ["c"]]),
        ],
        edges=[
            ("integer keys", ["__init__", "put", "get"], [[], [7, "x"], [7]]),
            ("empty map remove", ["__init__", "remove"], [[], ["a"]]),
        ],
        time_complexity="O(1) average, O(n) worst", space_complexity="O(n)",
        failures=["Appending a duplicate key instead of overwriting, so `get` returns "
                  "the stale value",
                  "Forgetting `% self.size`, causing an IndexError",
                  "Sharing one list across all buckets via `[[]] * n` — every bucket "
                  "becomes the same list"],
        nudge="`[[]] * 8` gives eight references to ONE list. Use a comprehension.",
        visual="Eight numbered vaults; the hash decides which vault, the chain handles "
               "collisions.",
        pseudocode="slot = hash(key) % size; scan the chain for the key; append if absent",
        tags=["core", "design"],
    ))

    P.append(design_problem(
        id="ds-time-map", title="The Chronicle Vault", realm="hashmap_highlands",
        difficulty="MEDIUM", cls_name="TimeMap", reference_cls=RefTimeMap,
        profile_weight=Q, secondary=["BINARY_SEARCH", "HASH_MAP"],
        statement="""
            Build a `TimeMap`:

            - `set(key, value, timestamp)` — store a value at a timestamp; timestamps for
              a given key arrive strictly increasing
            - `get(key, timestamp)` — return the value stored at the largest timestamp
              less than or equal to the one asked for, or `""` if none exists
        """,
        canonical="""
            class TimeMap:
                def __init__(self):
                    from collections import defaultdict
                    self.store = defaultdict(list)      # key -> [(timestamp, value)]

                def set(self, key, value, timestamp):
                    self.store[key].append((timestamp, value))
                    return None

                def get(self, key, timestamp):
                    import bisect
                    entries = self.store.get(key, [])
                    stamps = [t for t, _ in entries]
                    i = bisect.bisect_right(stamps, timestamp)
                    return entries[i - 1][1] if i else ""
        """,
        visible=[
            ("exact", ["__init__", "set", "get"], [[], ["a", "one", 1], ["a", 1]]),
            ("between", ["__init__", "set", "set", "get"],
             [[], ["a", "one", 1], ["a", "two", 4], ["a", 3]]),
        ],
        hidden=[
            ("before anything", ["__init__", "set", "get"], [[], ["a", "one", 5], ["a", 1]]),
            ("missing key", ["__init__", "get"], [[], ["ghost", 5]]),
            ("after everything", ["__init__", "set", "get"], [[], ["a", "one", 1], ["a", 99]]),
            ("two keys", ["__init__", "set", "set", "get"],
             [[], ["a", "x", 1], ["b", "y", 1], ["b", 1]]),
        ],
        edges=[("timestamp zero", ["__init__", "set", "get"], [[], ["a", "z", 0], ["a", 0]])],
        time_complexity="O(log n) per get", space_complexity="O(n)",
        failures=["Scanning the whole history per get is O(n)",
                  "`bisect_left` misses an exact timestamp match",
                  "Returning `None` instead of the empty string"],
        nudge="Timestamps arrive sorted, so the history is already a sorted array. That "
              "is a binary search waiting to happen.",
        visual="A shelf of dated entries; reach for the last one not after your date.",
        pseudocode="i = bisect_right(stamps, timestamp); return entries[i-1] if i else ''",
        tags=["core", "design"],
    ))

    P.append(design_problem(
        id="ds-undo-redo", title="The Twin Ledgers", realm="stack_queue_mines",
        difficulty="MEDIUM", cls_name="UndoStack", reference_cls=RefUndoStack,
        profile_weight=Q, secondary=["STACK"],
        statement="""
            Build an `UndoStack`:

            - `do(action)` — perform an action, return the list of actions in effect
            - `undo()` — revert the most recent action and return it, or `None`
            - `redo()` — reapply the most recently undone action and return it, or `None`

            A new `do` **clears the redo history** — this is the rule everyone forgets.
        """,
        canonical="""
            class UndoStack:
                def __init__(self):
                    self.done = []
                    self.undone = []

                def do(self, action):
                    self.done.append(action)
                    self.undone.clear()      # a new branch invalidates the redo future
                    return list(self.done)

                def undo(self):
                    if not self.done:
                        return None
                    action = self.done.pop()
                    self.undone.append(action)
                    return action

                def redo(self):
                    if not self.undone:
                        return None
                    action = self.undone.pop()
                    self.done.append(action)
                    return action
        """,
        visible=[
            ("do undo redo", ["__init__", "do", "undo", "redo"], [[], ["a"], [], []]),
            ("two actions", ["__init__", "do", "do", "undo"], [[], ["a"], ["b"], []]),
        ],
        hidden=[
            ("do clears redo",
             ["__init__", "do", "undo", "do", "redo"], [[], ["a"], [], ["b"], []]),
            ("undo past empty", ["__init__", "undo", "undo"], [[], [], []]),
            ("redo without undo", ["__init__", "do", "redo"], [[], ["a"], []]),
        ],
        edges=[("fresh redo", ["__init__", "redo"], [[], []])],
        time_complexity="O(1)", space_complexity="O(n)",
        failures=["Not clearing the redo stack on a new action, so redo replays a "
                  "history that no longer exists",
                  "Returning the wrong ledger from `do`"],
        nudge="Two stacks facing each other. The subtle rule is what a new action does to "
              "the redo side.",
        visual="Actions flow from done to undone and back — until a new action burns the "
               "undone pile.",
        pseudocode="do: push to done, clear undone. undo: done -> undone. redo: undone -> done",
        tags=["core", "design"],
    ))

    P.append(design_problem(
        id="ds-moving-window", title="The Rolling Register", realm="sliding_window_marsh",
        difficulty="EASY", cls_name="MovingWindow", reference_cls=RefMovingWindow,
        profile_weight=Q, secondary=["QUEUE", "SLIDING_WINDOW"],
        statement="""
            Build a `MovingWindow(size)` whose `add(value)` returns the sum of the most
            recent `size` values (fewer, before the window fills).
        """,
        canonical="""
            class MovingWindow:
                def __init__(self, size=3):
                    from collections import deque
                    self.size = size
                    self.window = deque()
                    self.total = 0

                def add(self, value):
                    self.window.append(value)
                    self.total += value
                    if len(self.window) > self.size:
                        self.total -= self.window.popleft()
                    return self.total
        """,
        visible=[
            ("fills up", ["__init__", "add", "add", "add", "add"],
             [[3], [1], [2], [3], [4]]),
            ("size one", ["__init__", "add", "add"], [[1], [5], [9]]),
        ],
        hidden=[
            ("negatives", ["__init__", "add", "add"], [[2], [-1], [-2]]),
            ("zeros", ["__init__", "add", "add"], [[2], [0], [0]]),
            ("large window", ["__init__", "add"], [[100], [7]]),
        ],
        edges=[("first value", ["__init__", "add"], [[3], [42]])],
        time_complexity="O(1) per add", space_complexity="O(size)",
        failures=["Re-summing the deque each call",
                  "Using a list and `pop(0)`, which is O(n)"],
        nudge="Keep a running total; subtract exactly what leaves.",
        visual="A line of values; the oldest steps out as a new one steps in.",
        pseudocode="append + add; if too long: popleft and subtract",
        tags=["design"],
    ))

    P.append(design_problem(
        id="sec-rate-limiter", title="The Gatekeeper", realm="sliding_window_marsh",
        difficulty="MEDIUM", cls_name="RateLimiter", reference_cls=RefRateLimiter,
        security=True, profile_weight=QS, secondary=["SLIDING_WINDOW", "QUEUE"],
        statement="""
            Build a `RateLimiter(window, limit)` with `allow(key, now)` returning `True`
            when the request is permitted.

            A request is permitted when fewer than `limit` requests for that key already
            fall inside the trailing `window` seconds — the interval `(now - window, now]`.
            Denied requests do **not** count toward the limit.

            Timestamps for a key are non-decreasing.
        """,
        canonical="""
            class RateLimiter:
                def __init__(self, window=10, limit=3):
                    from collections import defaultdict, deque
                    self.window = window
                    self.limit = limit
                    self.hits = defaultdict(deque)

                def allow(self, key, now):
                    q = self.hits[key]
                    while q and q[0] <= now - self.window:
                        q.popleft()               # expire what fell out of the window
                    if len(q) >= self.limit:
                        return False              # denied: do NOT record it
                    q.append(now)
                    return True
        """,
        visible=[
            ("under limit", ["__init__", "allow", "allow"], [[10, 2], ["a", 0], ["a", 1]]),
            ("over limit", ["__init__", "allow", "allow", "allow"],
             [[10, 2], ["a", 0], ["a", 1], ["a", 2]]),
        ],
        hidden=[
            ("window expires",
             ["__init__", "allow", "allow", "allow", "allow"],
             [[10, 2], ["a", 0], ["a", 1], ["a", 2], ["a", 11]]),
            ("keys are independent",
             ["__init__", "allow", "allow", "allow"],
             [[10, 1], ["a", 0], ["b", 0], ["a", 1]]),
            ("denied does not count",
             ["__init__", "allow", "allow", "allow", "allow"],
             [[10, 1], ["a", 0], ["a", 1], ["a", 2], ["a", 10]]),
        ],
        edges=[
            ("limit zero", ["__init__", "allow"], [[10, 0], ["a", 0]]),
            ("boundary is exclusive", ["__init__", "allow", "allow"],
             [[10, 1], ["a", 0], ["a", 10]]),
        ],
        time_complexity="O(1) amortized", space_complexity="O(limit) per key",
        failures=["Recording denied requests, which permanently locks out a caller",
                  "Using a single shared deque across every key",
                  "Off-by-one on expiry: `<=` versus `<` shifts the boundary by a second",
                  "Storing all history forever rather than expiring it"],
        nudge="A per-key sliding window of timestamps. Expire first, then decide, and only "
              "record what you actually allowed.",
        visual="Each key carries its own trailing window; old requests fall off the back.",
        pseudocode="""
            expire while q[0] <= now - window
            len(q) >= limit -> deny (record nothing)
            else            -> append(now), allow
        """,
        tags=["security", "design", "transfer"],
    ))

    P.append(design_problem(
        id="sec-alert-logger", title="The Cooldown Herald", realm="hashmap_highlands",
        difficulty="EASY", cls_name="AlertLogger", reference_cls=RefEventLogger,
        security=True, profile_weight=QS, secondary=["HASH_MAP"],
        statement="""
            Build an `AlertLogger(cooldown)` with `should_print(message, timestamp)`.

            A message may be printed only if it has not been printed within the last
            `cooldown` seconds. Printing refreshes its timer; a suppressed message does
            **not**.
        """,
        canonical="""
            class AlertLogger:
                def __init__(self, cooldown=10):
                    self.cooldown = cooldown
                    self.last = {}

                def should_print(self, message, timestamp):
                    previous = self.last.get(message)
                    if previous is not None and timestamp < previous + self.cooldown:
                        return False           # suppressed: do NOT refresh the timer
                    self.last[message] = timestamp
                    return True
        """,
        visible=[
            ("first is printed", ["__init__", "should_print"], [[10], ["boot", 1]]),
            ("suppressed", ["__init__", "should_print", "should_print"],
             [[10], ["boot", 1], ["boot", 5]]),
        ],
        hidden=[
            ("after cooldown", ["__init__", "should_print", "should_print"],
             [[10], ["boot", 1], ["boot", 11]]),
            ("different messages", ["__init__", "should_print", "should_print"],
             [[10], ["a", 1], ["b", 1]]),
            ("suppression does not extend",
             ["__init__", "should_print", "should_print", "should_print"],
             [[10], ["a", 0], ["a", 5], ["a", 10]]),
        ],
        edges=[("cooldown zero", ["__init__", "should_print", "should_print"],
                [[0], ["a", 1], ["a", 1]])],
        time_complexity="O(1)", space_complexity="O(distinct messages)",
        failures=["Refreshing the timestamp on a suppressed message, which silences the "
                  "alert forever under sustained load",
                  "Using `<=` and letting a message through one second early"],
        nudge="Only a message you actually printed may reset its own clock.",
        visual="Each message carries a timer that only a successful print rewinds.",
        pseudocode="timestamp < last + cooldown -> False (unchanged); else record and True",
        tags=["security", "design", "transfer"],
    ))

    return P
