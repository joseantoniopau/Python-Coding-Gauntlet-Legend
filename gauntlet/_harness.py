"""Standalone in-child test harness. Never imports the gauntlet package.

Invoked as:  python3 _harness.py <payload.json> <result.json>

The payload carries the player's source, the entry-point spec and the test
batch. Results are written to <result.json> so the player's own stdout stays
pristine and can be shown in the battle log verbatim.
"""
import json
import math
import os
import signal
import sys
import time
import traceback

RECURSION_LIMIT = 20000


class TestTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise TestTimeout()


# --- the per-test deadline, which is the one thing that is not portable.
#
# On POSIX we use SIGALRM, which interrupts the interpreter wherever it is. On
# Windows there is no SIGALRM, so a watchdog thread asks the main thread to
# raise instead. That is strictly weaker: it can only land between bytecodes, so
# a player whose code blocks inside a single C call (a huge int multiply, say)
# will not be caught here. The parent's wall-clock kill still catches them, so
# the difference the player sees is "this test timed out" versus "your code ran
# too long" — worse diagnostics, same safety.
_HAS_SIGALRM = hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")

if _HAS_SIGALRM:
    def _deadline_install():
        signal.signal(getattr(signal, "SIGALRM"), _alarm)

    def _deadline_start(seconds):
        signal.setitimer(signal.ITIMER_REAL, seconds)

    def _deadline_clear():
        signal.setitimer(signal.ITIMER_REAL, 0)
else:
    import ctypes
    import threading

    _watchdog = None
    _main_tid = threading.get_ident()

    def _deadline_install():
        return None

    def _raise_in_main():
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(_main_tid), ctypes.py_object(TestTimeout))

    def _deadline_start(seconds):
        global _watchdog
        _deadline_clear()
        if seconds <= 0:
            return
        _watchdog = threading.Timer(seconds, _raise_in_main)
        _watchdog.daemon = True
        _watchdog.start()

    def _deadline_clear():
        global _watchdog
        if _watchdog is not None:
            _watchdog.cancel()
            _watchdog = None
        # A watchdog that fired microseconds before we cancelled leaves an async
        # exception queued against the main thread. Drain it, or it lands on
        # whatever innocent statement runs next.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(_main_tid), ctypes.c_void_p(0))


MAP_TAG = "__map__"


def _decode(value):
    """Undo the build-side tagging so dicts keyed by non-strings survive JSON."""
    if isinstance(value, dict):
        if len(value) == 1 and MAP_TAG in value and isinstance(value[MAP_TAG], list):
            return {_decode(k): _decode(v) for k, v in value[MAP_TAG]}
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _freeze(value):
    """Hashable, order-insensitive projection used by the set comparators."""
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_freeze(v) for v in value))
    if isinstance(value, set):
        return ("set", tuple(sorted((repr(_freeze(v)) for v in value))))
    if isinstance(value, dict):
        return ("map", tuple(sorted((repr(k), repr(_freeze(v))) for k, v in value.items())))
    return ("val", value)


def _sorted_key(value):
    return repr(_freeze(value))


def compare(got, expected, mode):
    """Return (ok, human_reason)."""
    try:
        if mode == "exact":
            return got == expected, ""
        if mode == "float":
            if isinstance(got, (int, float)) and isinstance(expected, (int, float)):
                return math.isclose(got, expected, rel_tol=1e-6, abs_tol=1e-9), ""
            return False, "expected a number"
        if mode == "float_list":
            if not isinstance(got, (list, tuple)) or len(got) != len(expected):
                return False, "expected a list of %d numbers" % len(expected)
            for g, e in zip(got, expected):
                if not isinstance(g, (int, float)):
                    return False, "expected every element to be a number"
                if not math.isclose(g, e, rel_tol=1e-6, abs_tol=1e-9):
                    return False, ""
            return True, ""
        if mode == "set":
            if not isinstance(got, (list, tuple, set)):
                return False, "expected a collection"
            return sorted(map(_sorted_key, got)) == sorted(map(_sorted_key, expected)), ""
        if mode == "sorted":
            if not isinstance(got, (list, tuple)):
                return False, "expected a list"
            return sorted(got, key=_sorted_key) == sorted(expected, key=_sorted_key), ""
        if mode == "nested_set":
            # list of lists, inner order and outer order both irrelevant
            if not isinstance(got, (list, tuple)):
                return False, "expected a list of lists"
            g = sorted([sorted(map(_sorted_key, row)) for row in got])
            e = sorted([sorted(map(_sorted_key, row)) for row in expected])
            return g == e, ""
        if mode == "bool":
            return bool(got) == bool(expected), ""
        if mode == "any_of":
            return any(got == alt for alt in expected), ""
        return got == expected, ""
    except TypeError as exc:
        return False, "values could not be compared (%s)" % exc


def _short(value, limit=300):
    try:
        text = repr(value)
    except Exception:
        text = "<unrepresentable>"
    if len(text) > limit:
        text = text[:limit] + " ... (truncated)"
    return text


# --- argument / result adapters -------------------------------------------
# Tree problems must hand the player a real linked TreeNode, not a list, or the
# encounter stops resembling an interview. Tests still travel as level-order
# lists with None for absent children.

def _to_tree(values, ns):
    node_cls = ns.get("TreeNode")
    if node_cls is None or not values:
        return None
    root = node_cls(values[0])
    queue = [root]
    i = 1
    head = 0
    while head < len(queue) and i < len(values):
        node = queue[head]
        head += 1
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.left = node_cls(v)
                queue.append(node.left)
        if i < len(values):
            v = values[i]; i += 1
            if v is not None:
                node.right = node_cls(v)
                queue.append(node.right)
    return root


def _from_tree(node, ns):
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


def _to_linked(values, ns):
    """Level with the tree adapter: linked-list problems must hand the player a
    real ListNode chain, not a Python list wearing a costume."""
    node_cls = ns.get("ListNode")
    if node_cls is None or not values:
        return None
    head = node_cls(values[0])
    cur = head
    for value in values[1:]:
        cur.next = node_cls(value)
        cur = cur.next
    return head


def _to_linked_cycle(spec, ns):
    """[values, pos] -> a chain whose tail links back to index `pos` (-1: none)."""
    values, pos = (list(spec) + [-1])[:2]
    node_cls = ns.get("ListNode")
    if node_cls is None or not values:
        return None
    nodes = [node_cls(v) for v in values]
    for node, nxt in zip(nodes, nodes[1:]):
        node.next = nxt
    if isinstance(pos, int) and 0 <= pos < len(nodes):
        nodes[-1].next = nodes[pos]
    return nodes[0]


def _from_linked(node, ns):
    """Walk a returned chain back into a list. The seen-set is not decoration: a
    player who mis-wires a reversal produces a ring, and without it the grader
    hangs instead of failing."""
    out, seen = [], set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        out.append(node.val)
        node = node.next
    return out


_ARG_ADAPTERS = {"tree": _to_tree, "linked": _to_linked,
                 "linked_cycle": _to_linked_cycle}
_RESULT_ADAPTERS = {"tree": _from_tree, "linked": _from_linked}


def _adapt_args(ns, entry, args):
    adapters = entry.get("arg_adapters")
    if not adapters:
        return args
    out = []
    for value, name in zip(args, list(adapters) + [None] * len(args)):
        out.append(_ARG_ADAPTERS[name](value, ns) if name else value)
    return out


def _adapt_result(ns, entry, value):
    name = entry.get("result_adapter")
    return _RESULT_ADAPTERS[name](value, ns) if name else value


def run_function_test(ns, entry, test):
    fn = ns.get(entry["name"])
    if fn is None or not callable(fn):
        raise NameError("no function named %r was defined" % entry["name"])
    args = _decode(json.loads(json.dumps(test.get("args", []))))
    args = _adapt_args(ns, entry, args)
    kwargs = test.get("kwargs", {})
    return _adapt_result(ns, entry, fn(*args, **kwargs))


def run_class_ops_test(ns, entry, test):
    """Design/OOP problems: build the object, replay an operation trace."""
    cls = ns.get(entry["name"])
    if cls is None:
        raise NameError("no class named %r was defined" % entry["name"])
    ops = test["ops"]
    argsets = _decode(test.get("args", [[] for _ in ops]))
    out = []
    obj = None
    for op, args in zip(ops, argsets):
        if op == "__init__":
            obj = cls(*args)
            out.append(None)
            continue
        if obj is None:
            obj = cls()
        method = getattr(obj, op, None)
        if method is None:
            raise AttributeError("object has no method %r" % op)
        out.append(method(*args))
    return out


def run_tests(ns, entry, tests, default_timeout_ms):
    results = []
    kind = entry.get("kind", "function")
    for index, test in enumerate(tests):
        timeout_ms = test.get("timeout_ms", default_timeout_ms)
        record = {
            "index": index,
            "name": test.get("name") or "test %d" % (index + 1),
            "hidden": bool(test.get("hidden")),
            "kind": test.get("kind", "correctness"),
            "status": "pass",
            "ms": 0.0,
            "message": "",
            "got": None,
            "expected": None,
            "reveal": bool(test.get("reveal", True)),
        }
        _deadline_start(timeout_ms / 1000.0)
        started = time.perf_counter()
        try:
            if kind == "class_ops":
                got = run_class_ops_test(ns, entry, test)
            else:
                got = run_function_test(ns, entry, test)
            elapsed = (time.perf_counter() - started) * 1000.0
            _deadline_clear()
            record["ms"] = round(elapsed, 3)
            ok, reason = compare(got, _decode(test["expected"]),
                                 test.get("cmp", "exact"))
            if not ok:
                record["status"] = "fail"
                record["message"] = reason or "returned the wrong value"
                record["got"] = _short(got)
                record["expected"] = _short(_decode(test["expected"]))
        except TestTimeout:
            _deadline_clear()
            record["status"] = "timeout"
            record["ms"] = timeout_ms
            record["message"] = "ran longer than %dms" % timeout_ms
        except RecursionError:
            _deadline_clear()
            record["status"] = "exception"
            record["message"] = "RecursionError: recursion went too deep (missing or wrong base case?)"
            record["exc_type"] = "RecursionError"
        except Exception as exc:  # noqa: BLE001 - player code, anything goes
            _deadline_clear()
            record["status"] = "exception"
            record["message"] = "%s: %s" % (type(exc).__name__, exc)
            record["exc_type"] = type(exc).__name__
            record["traceback"] = _player_traceback()
        results.append(record)
        if record["status"] != "pass" and test.get("stop_on_fail"):
            break
    return results


def _player_traceback():
    """Trim harness frames so the player only sees their own code."""
    lines = traceback.format_exc().splitlines()
    keep, seen = [], False
    for line in lines:
        if "<player>" in line:
            seen = True
        if seen:
            keep.append(line)
    if not keep:
        keep = lines[-3:]
    return "\n".join(keep[-12:])


def main():
    payload_path, result_path = sys.argv[1], sys.argv[2]
    with open(payload_path) as fh:
        payload = json.load(fh)

    sys.setrecursionlimit(RECURSION_LIMIT)
    _deadline_install()
    preamble = payload["entry"].get("preamble") or ""
    if preamble:
        source = preamble.rstrip() + "\n\n" + payload["source"]
        payload["source"] = source

    outcome = {"ok": False, "phase": "compile", "tests": [], "stdout": "", "stderr": ""}
    source = payload["source"]
    preamble_lines = preamble.rstrip().count("\n") + 2 if preamble else 0
    outcome["preamble_lines"] = preamble_lines
    ns = {"__name__": "__player__"}

    try:
        compiled = compile(source, "<player>", "exec")
    except SyntaxError as exc:
        outcome["phase"] = "syntax"
        outcome["error"] = {
            "type": "SyntaxError",
            "message": str(exc.msg),
            "line": (exc.lineno - preamble_lines) if exc.lineno else None,
            "offset": exc.offset,
            "text": (exc.text or "").rstrip(),
        }
        _emit(result_path, outcome)
        return
    except Exception as exc:  # noqa: BLE001
        outcome["phase"] = "syntax"
        outcome["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _emit(result_path, outcome)
        return

    try:
        _deadline_start(payload.get("import_timeout_ms", 4000) / 1000.0)
        exec(compiled, ns)  # noqa: S102 - this is the whole point, inside a sandbox
        _deadline_clear()
    except TestTimeout:
        outcome["phase"] = "toplevel"
        outcome["error"] = {"type": "Timeout", "message": "module-level code never finished"}
        _emit(result_path, outcome)
        return
    except Exception as exc:  # noqa: BLE001
        _deadline_clear()
        outcome["phase"] = "toplevel"
        outcome["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": _player_traceback(),
        }
        _emit(result_path, outcome)
        return

    outcome["phase"] = "tests"
    try:
        outcome["tests"] = run_tests(
            ns, payload["entry"], payload["tests"], payload.get("timeout_ms", 3000)
        )
        outcome["ok"] = True
    except Exception as exc:  # noqa: BLE001
        outcome["error"] = {"type": type(exc).__name__, "message": str(exc)}
        outcome["ok"] = False
    _emit(result_path, outcome)


def _emit(path, outcome):
    with open(path, "w") as fh:
        json.dump(outcome, fh)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
