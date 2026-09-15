"""Standalone in-child test harness. Never imports the gauntlet package.

Invoked as:  python3 _harness.py <payload.json> <result.json>

The payload carries the player's source, the entry-point spec and the test
batch. Results are written to <result.json> so the player's own stdout stays
pristine and can be shown in the battle log verbatim.
"""
import dis
import json
import math
import os
import re
import signal
import sys
import time
import traceback
from inspect import CO_GENERATOR, CO_COROUTINE, CO_ITERABLE_COROUTINE, CO_ASYNC_GENERATOR

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
# encounter stops resembling a timed practical. Tests still travel as level-order
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


def run_project_tests(project_dir, test_files, timeout_ms):
    """Run a Mini-Repo's own test files and report each test function.

    This is deliberately not unittest or pytest: the child runs with -I -S and
    must not depend on anything outside the standard library being importable.
    A test is a module-level callable whose name starts with `test`, which is
    the convention both frameworks share and the only part of them we need.
    """
    import importlib.util

    results = []
    for rel in test_files:
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            results.append({"name": rel, "status": "exception",
                            "message": "no such test file", "ms": 0.0})
            continue
        spec = importlib.util.spec_from_file_location(
            "projtest_" + re.sub(r"\W", "_", rel), path)
        module = importlib.util.module_from_spec(spec)
        try:
            _deadline_start(timeout_ms / 1000.0)
            spec.loader.exec_module(module)
            _deadline_clear()
        except TestTimeout:
            _deadline_clear()
            results.append({"name": rel, "status": "timeout",
                            "message": "the test file never finished importing",
                            "ms": timeout_ms})
            continue
        except Exception as exc:  # noqa: BLE001
            _deadline_clear()
            results.append({"name": rel, "status": "exception",
                            "message": "%s: %s" % (type(exc).__name__, exc),
                            "ms": 0.0, "traceback": _player_traceback()})
            continue

        names = [n for n in sorted(dir(module))
                 if n.startswith("test") and callable(getattr(module, n))]
        if not names:
            results.append({"name": rel, "status": "exception",
                            "message": "no test functions found", "ms": 0.0})
        for name in names:
            record = {"name": "%s::%s" % (rel, name), "status": "pass",
                      "ms": 0.0, "message": ""}
            started = time.perf_counter()
            try:
                _deadline_start(timeout_ms / 1000.0)
                getattr(module, name)()
                _deadline_clear()
            except TestTimeout:
                _deadline_clear()
                record["status"] = "timeout"
                record["message"] = "ran longer than %dms" % timeout_ms
            except AssertionError as exc:
                _deadline_clear()
                record["status"] = "fail"
                record["message"] = str(exc) or "assertion failed"
                record["traceback"] = _player_traceback()
            except Exception as exc:  # noqa: BLE001
                _deadline_clear()
                record["status"] = "exception"
                record["message"] = "%s: %s" % (type(exc).__name__, exc)
                record["traceback"] = _player_traceback()
            record["ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            results.append(record)
    return results


class TraceStopped(BaseException):
    """A bounded teaching recording has ended; it is not a failed test."""


class TraceOutput:
    encoding = "utf-8"

    def __init__(self):
        self.text = ""
        self.truncated = False

    def write(self, text):
        if type(text) is not str:
            raise TypeError("stdout.write needs a string")
        room = 4096 - len(self.text)
        self.text += text[:room]
        self.truncated = self.truncated or len(text) > room
        return len(text)

    def flush(self):
        pass

    def isatty(self):
        return False


def trace_snapshot(value, depth=3, budget=None, seen=None):
    """A detached JSON snapshot, with no repr, properties or object iteration.

    Exact built-in types only: even list/dict subclasses may override iteration
    or formatting. Containers share a node budget and cycles never recurse.
    """
    if budget is None:
        budget = [100]
    if seen is None:
        seen = set()
    budget[0] -= 1
    if budget[0] < 0:
        return "<snapshot limit>"
    kind = type(value)
    if value is None or kind is bool:
        return value
    if kind is int:
        return value if value.bit_length() <= 256 else "<large integer omitted>"
    if kind is float:
        return value if math.isfinite(value) else "<non-finite float>"
    if kind is str:
        return value if len(value) <= 160 else value[:160] + "…"
    if kind not in (list, tuple, dict, set, frozenset):
        # Calling type.__getattribute__ bypasses a custom metaclass hook.
        name = type.__getattribute__(kind, "__name__")
        return "<" + name[:60] + " omitted>"
    if id(value) in seen:
        return "<cycle>"
    if depth <= 0:
        return "<container depth limit>"
    seen.add(id(value))
    try:
        if kind is dict:
            rows = []
            for key, item in value.items():
                if len(rows) >= 16 or budget[0] <= 0:
                    break
                rows.append((trace_snapshot(key, depth - 1, budget, seen),
                             trace_snapshot(item, depth - 1, budget, seen)))
            # Preserve common string-key dictionaries as dictionaries. Tagged
            # entries preserve distinct nonstring/truncated keys without coercion.
            simple = len(value) <= 16 and all(type(k) is str and len(k) <= 160 for k in value)
            if simple and len(rows) == len(value):
                return dict(rows)
            return {"$type": "dict", "entries": [list(row) for row in rows],
                    "omitted": len(value) - len(rows)}
        items = []
        for item in value:
            if len(items) >= 16 or budget[0] <= 0:
                break
            items.append(trace_snapshot(item, depth - 1, budget, seen))
        if kind is list and len(items) == len(value):
            return items
        return {"$type": type.__getattribute__(kind, "__name__"), "items": items,
                "omitted": len(value) - len(items)}
    finally:
        seen.remove(id(value))


def _trace_exception(exc, line=None):
    name = type.__getattribute__(type(exc), "__name__")[:80]
    # Exception subclasses may override __str__, __repr__, and args access.
    args = BaseException.args.__get__(exc, type(exc))
    message = args[0][:240] if args and type(args[0]) is str else "The program raised " + name + "."
    return {"type": name, "message": message, "line": line}


# sys.settrace reports a suspended generator/coroutine as "return", followed
# by "call" when it resumes. Use this interpreter's bytecode names, not opcode
# numbers (which changed between CPython 3.11, 3.12, 3.13 and 3.14). Reading the
# opcode byte avoids dis.get_instructions(), whose argument formatting could
# call repr() on a player-supplied object in a replaced code object's constants.
_TRACE_OPNAMES = tuple(dis.opname)
_TRACE_RESUMABLE = CO_GENERATOR | CO_COROUTINE | CO_ITERABLE_COROUTINE | CO_ASYNC_GENERATOR
_TRACE_ASYNC = CO_COROUTINE | CO_ITERABLE_COROUTINE | CO_ASYNC_GENERATOR
_TRACE_CPYTHON = sys.implementation.name == "cpython"
_TRACE_RETURNS = frozenset(("RETURN_VALUE", "RETURN_CONST"))
_TRACE_YIELDS = frozenset(("YIELD_VALUE", "YIELD_FROM"))


def _trace_opcode(frame):
    code = frame.f_code.co_code
    offset = frame.f_lasti
    opcode = _TRACE_OPNAMES[code[offset]] if 0 <= offset < len(code) else ""
    # CPython 3.13 reports suspension at the following RESUME instruction;
    # 3.11, 3.12 and 3.14 report YIELD_VALUE itself. Instructions are two-byte
    # code units in all supported versions. Exception unwinds at RESUME are
    # distinguished by the preceding trace event in record(), below.
    if opcode == "RESUME" and offset >= 2:
        previous = _TRACE_OPNAMES[code[offset - 2]]
        if previous in _TRACE_YIELDS:
            return previous
    return opcode


def trace_program(payload):
    source, entry = payload["source"], payload["entry"]
    preamble = entry.get("preamble") or ""
    offset = preamble.rstrip().count("\n") + 2 if preamble else 0
    compiled_source = preamble.rstrip() + "\n\n" + source if preamble else source
    outcome = {"ok": False, "frames": [], "truncated": False,
               "truncation_reason": "", "exception": None, "output": None,
               "stdout": "", "stdout_truncated": False}
    try:
        compiled = compile(compiled_source, "<player>", "exec")
    except SyntaxError as exc:
        outcome["exception"] = {"type": "SyntaxError", "message": exc.msg,
                                "line": max(1, (exc.lineno or 1) - offset)}
        return outcome
    except Exception as exc:
        outcome["exception"] = _trace_exception(exc)
        return outcome
    capture = TraceOutput()
    previous_stdout = sys.stdout
    frames = outcome["frames"]
    max_steps = payload.get("max_steps", 400)
    snapshot_depth = payload.get("snapshot_depth", 3)
    frame_ids, next_id, trace_bytes = {}, 0, 0
    suspended, last_events = set(), {}
    last_line = None

    def stop(reason):
        outcome["truncated"] = True
        outcome["truncation_reason"] = reason
        raise TraceStopped()

    def record(frame, event, arg):
        nonlocal next_id, trace_bytes, last_line
        if frame.f_code.co_filename != "<player>":
            return None
        line = frame.f_lineno - offset
        if line < 1:
            return record
        if event not in ("call", "line", "return", "exception"):
            return record
        if len(frames) >= max_steps:
            stop("step limit reached")
        parent, depth = frame.f_back, 0
        while parent is not None:
            if parent.f_code.co_filename == "<player>" and parent.f_lineno > offset:
                depth += 1
            if depth >= 48:
                stop("call depth limit reached")
            parent = parent.f_back
        fid = id(frame)
        resumable = frame.f_code.co_flags & _TRACE_RESUMABLE
        if resumable and not _TRACE_CPYTHON:
            stop("generator/coroutine tracing is unsupported by this interpreter")
        if fid not in frame_ids:
            next_id += 1
            frame_ids[fid] = next_id
        raw_event = event
        if event == "call" and fid in suspended:
            event = "resume"
            suspended.remove(fid)
        elif event == "return":
            opcode = _trace_opcode(frame)
            if resumable and opcode in _TRACE_YIELDS and last_events.get(fid) != "exception":
                event = "suspend" if frame.f_code.co_flags & _TRACE_ASYNC else "yield"
                suspended.add(fid)
            elif opcode in _TRACE_RETURNS:
                # await/yield-from completion raises an internal StopIteration
                # trace event before a real return, sometimes on the same line.
                pass
            elif last_events.get(fid) == "exception" or opcode in ("RAISE_VARARGS", "RERAISE", "CLEANUP_THROW"):
                # throw()/close() can exit at the suspended yield instruction;
                # an exception return is neither a yield nor a returned None.
                event = "unwind"
            elif resumable and opcode not in _TRACE_RETURNS:
                stop("generator/coroutine boundary is unsupported by this interpreter")
        local_values, budget = {}, [100]
        local_count = 0
        for name, value in frame.f_locals.items():
            if name.startswith("__"):
                continue
            if local_count >= 24 or budget[0] <= 0:
                local_values["…"] = "<remaining locals omitted>"
                break
            local_values[name[:120]] = trace_snapshot(value, snapshot_depth, budget)
            local_count += 1
        item = {"line": line, "event": event, "function": frame.f_code.co_name,
                "depth": depth, "call_id": frame_ids[fid],
                "locals": local_values, "stdout": capture.text}
        if event in ("return", "yield"):
            item["value"] = trace_snapshot(arg, snapshot_depth)
        # Async-generator yield arguments are private interpreter wrappers.
        # A suspend event exposes locals without inventing an unwrapped value.
        elif event == "exception":
            item["exception"] = _trace_exception(arg[1], line)
        trace_bytes += len(json.dumps(item, ensure_ascii=True))
        if trace_bytes > 512 * 1024:
            stop("recording size limit reached")
        frames.append(item)
        last_line = line
        if event in ("return", "unwind"):
            frame_ids.pop(fid, None)
            suspended.discard(fid)
            last_events.pop(fid, None)
        else:
            last_events[fid] = raw_event
        return record

    ns = {"__name__": "__player__"}
    try:
        sys.stdout = capture
        _deadline_start(payload.get("timeout_ms", 1200) / 1000.0)
        sys.settrace(record)
        exec(compiled, ns)  # noqa: S102 - only this isolated child executes Python
        if entry.get("kind", "function") == "class_ops":
            value = run_class_ops_test(ns, entry, payload["case"])
        else:
            value = run_function_test(ns, entry, payload["case"])
        sys.settrace(None)
        outcome["output"] = trace_snapshot(value, snapshot_depth)
        outcome["ok"] = True
    except TraceStopped:
        pass
    except TestTimeout:
        outcome["truncated"] = True
        outcome["truncation_reason"] = "execution time limit reached"
        outcome["exception"] = {"type": "Timeout", "message": "This trace reached its execution time limit.", "line": last_line}
    except BaseException as exc:  # player SystemExit must also produce a trace
        tb = BaseException.__traceback__.__get__(exc, type(exc))
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == "<player>" and tb.tb_lineno > offset:
                last_line = tb.tb_lineno - offset
            tb = tb.tb_next
        outcome["exception"] = _trace_exception(exc, last_line)
    finally:
        sys.settrace(None)
        _deadline_clear()
        sys.stdout = previous_stdout
    outcome["stdout"] = capture.text
    outcome["stdout_truncated"] = capture.truncated
    return outcome


def main():
    payload_path, result_path = sys.argv[1], sys.argv[2]
    with open(payload_path) as fh:
        payload = json.load(fh)

    # A project is several files that import each other. The child runs with -I,
    # which deliberately keeps the script's directory off sys.path, so the
    # project has to be put there explicitly or nothing in it can import
    # anything else in it.
    project_dir = payload.get("project_dir")
    if project_dir:
        sys.path.insert(0, project_dir)

    sys.setrecursionlimit(RECURSION_LIMIT)
    _deadline_install()

    if payload.get("mode") == "trace":
        _emit(result_path, trace_program(payload))
        return

    # A Mini-Repo is graded by running the project's own tests, not by calling a
    # function the player wrote, so it never reaches the compile path below.
    if payload.get("mode") == "project":
        outcome = {"ok": False, "phase": "tests", "tests": [],
                   "stdout": "", "stderr": ""}
        try:
            outcome["tests"] = run_project_tests(
                project_dir, payload.get("test_files", []),
                payload.get("timeout_ms", 3000))
            outcome["ok"] = True
        except Exception as exc:  # noqa: BLE001
            outcome["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _emit(result_path, outcome)
        return
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
