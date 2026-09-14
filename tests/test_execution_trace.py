"""Real child-process traces; no game, corpus, or save database is needed."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gauntlet import sandbox


class ExecutionTraceTests(unittest.TestCase):
    def trace(self, source, args=(), **opts):
        return sandbox.trace_program(source, {"kind": "function", "name": "f"},
                                     {"name": "visible example", "args": list(args)}, **opts)

    def test_loop_records_real_changing_locals_and_return(self):
        out = self.trace("def f(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total\n", [[2, 4, 7]])
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], 13)
        before_add = [f["locals"]["total"] for f in out["frames"] if f["line"] == 4 and f["event"] == "line"]
        self.assertEqual(before_add, [0, 2, 6])
        self.assertTrue(any(f["event"] == "return" and f.get("value") == 13 for f in out["frames"]))

    def test_calls_keep_distinct_frames_and_depth(self):
        out = self.trace("def double(x):\n    return x * 2\ndef f(n):\n    answer = double(n)\n    return answer\n", [5])
        calls = [f for f in out["frames"] if f["event"] == "call"]
        outer = next(f for f in calls if f["function"] == "f")
        inner = next(f for f in calls if f["function"] == "double")
        self.assertGreater(inner["depth"], outer["depth"])
        self.assertNotEqual(inner["call_id"], outer["call_id"])
        self.assertEqual(out["output"], 10)

    def test_generator_yields_resume_one_call_and_final_return(self):
        out = self.trace("def numbers():\n    x = 1\n    yield x\n    x += 1\n    yield x\n    return 9\ndef f():\n    gen = numbers()\n    values = [next(gen), next(gen)]\n    try:\n        next(gen)\n    except StopIteration as ended:\n        return [values, ended.value]\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], [[1, 2], 9])
        events = [f for f in out["frames"] if f["function"] == "numbers"]
        self.assertEqual(len({f["call_id"] for f in events}), 1)
        boundaries = [f for f in events if f["event"] != "line"]
        self.assertEqual([f["event"] for f in boundaries],
                         ["call", "yield", "resume", "yield", "resume", "return"])
        self.assertEqual([f["value"] for f in events if f["event"] == "yield"], [1, 2])
        self.assertEqual([f["locals"]["x"] for f in events if f["event"] == "resume"], [1, 2])
        self.assertEqual(events[-1]["value"], 9)

    def test_generator_delegation_send_and_none_yield_are_not_returns(self):
        out = self.trace("def inner():\n    value = yield None\n    yield value\n    return 7\ndef outer():\n    result = yield from inner()\n    return result\ndef f():\n    gen = outer()\n    values = [next(gen), gen.send(4)]\n    try:\n        next(gen)\n    except StopIteration as ended:\n        return [values, ended.value]\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], [[None, 4], 7])
        calls = {}
        for name in ("inner", "outer"):
            events = [f for f in out["frames"] if f["function"] == name]
            calls[name] = {f["call_id"] for f in events}
            self.assertEqual(len(calls[name]), 1)
            self.assertEqual([f["value"] for f in events if f["event"] == "yield"], [None, 4])
            self.assertEqual(sum(f["event"] == "resume" for f in events), 2)
            self.assertEqual(events[-1]["event"], "return")
            self.assertEqual(events[-1]["value"], 7)
        self.assertNotEqual(calls["inner"], calls["outer"])

    def test_generator_throw_and_close_are_unwinds_not_new_yields(self):
        out = self.trace("def numbers():\n    yield 1\n    yield 2\ndef f():\n    first = numbers()\n    next(first)\n    try:\n        first.throw(ValueError('stop'))\n    except ValueError:\n        pass\n    second = numbers()\n    next(second)\n    second.close()\n    return 8\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], 8)
        events = [f for f in out["frames"] if f["function"] == "numbers"]
        self.assertEqual(len({f["call_id"] for f in events}), 2)
        self.assertEqual(sum(f["event"] == "call" for f in events), 2)
        self.assertEqual(sum(f["event"] == "yield" for f in events), 2)
        self.assertEqual(sum(f["event"] == "resume" for f in events), 2)
        self.assertEqual(sum(f["event"] == "unwind" for f in events), 2)
        self.assertFalse(any(f["event"] == "return" for f in events))

    def test_coroutine_suspends_resumes_and_returns_without_an_event_loop(self):
        # An awaitable that actually suspends avoids creating sockets or an
        # event loop inside the network-denied child.
        out = self.trace("class Pause:\n    def __await__(self):\n        yield None\n        return 5\nasync def work():\n    n = 3\n    n += await Pause()\n    return n\ndef f():\n    coro = work()\n    first = coro.send(None)\n    try:\n        coro.send(None)\n    except StopIteration as ended:\n        return [first, ended.value]\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], [None, 8])
        events = [f for f in out["frames"] if f["function"] == "work"]
        self.assertEqual(len({f["call_id"] for f in events}), 1)
        self.assertEqual([f["event"] for f in events if f["event"] not in ("line", "exception")],
                         ["call", "suspend", "resume", "return"])
        self.assertEqual(next(f for f in events if f["event"] == "resume")["locals"]["n"], 3)
        self.assertEqual(events[-1]["value"], 8)
        self.assertNotIn("value", next(f for f in events if f["event"] == "suspend"))

    def test_coroutine_return_await_on_same_line_is_a_real_return(self):
        out = self.trace("class Pause:\n    def __await__(self):\n        yield None\n        return 5\nasync def work():\n    return await Pause()\ndef f():\n    coro = work()\n    coro.send(None)\n    try:\n        coro.send(None)\n    except StopIteration as ended:\n        return ended.value\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], 5)
        events = [f for f in out["frames"] if f["function"] == "work"]
        self.assertEqual(events[-1]["event"], "return")
        self.assertEqual(events[-1]["value"], 5)
        self.assertEqual(len({f["call_id"] for f in events}), 1)

    def test_async_generator_suspend_resume_keeps_call_identity(self):
        out = self.trace("async def numbers():\n    n = 1\n    yield n\n    n += 1\n    yield n\ndef f():\n    gen = numbers()\n    values = []\n    for i in range(3):\n        request = gen.__anext__()\n        try:\n            request.send(None)\n        except StopIteration as ended:\n            values.append(ended.value)\n        except StopAsyncIteration:\n            break\n    return values\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], [1, 2])
        events = [f for f in out["frames"] if f["function"] == "numbers"]
        self.assertEqual(len({f["call_id"] for f in events}), 1)
        self.assertEqual([f["event"] for f in events if f["event"] != "line"],
                         ["call", "suspend", "resume", "suspend", "resume", "return"])
        self.assertTrue(all("value" not in f for f in events if f["event"] == "suspend"))
        self.assertNotIn("async_generator_wrapped_value", json.dumps(events))

    def test_preamble_lines_do_not_shift_editor_highlight(self):
        out = sandbox.trace_program("def f(n):\n    return twice(n)\n",
            {"kind": "function", "name": "f", "preamble": "def twice(n):\n    return n * 2"}, {"args": [4]})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], 8)
        self.assertTrue(all(f["line"] in (1, 2) for f in out["frames"]))
        self.assertFalse(any(f["function"] == "twice" for f in out["frames"]))

    def test_exception_is_visible_and_caught_exception_is_not_terminal(self):
        out = self.trace("def f():\n    x = 1\n    return x / 0\n")
        self.assertFalse(out["ok"])
        self.assertEqual(out["exception"]["type"], "ZeroDivisionError")
        self.assertEqual(out["exception"]["line"], 3)
        self.assertTrue(any(f["event"] == "exception" for f in out["frames"]))
        caught = self.trace("def f():\n    try:\n        return 1 / 0\n    except ZeroDivisionError:\n        return 7\n")
        self.assertTrue(caught["ok"])
        self.assertIsNone(caught["exception"])
        self.assertEqual(caught["output"], 7)

    def test_infinite_loop_returns_bounded_partial_trace(self):
        start = time.monotonic()
        out = self.trace("def f():\n    n = 0\n    while True:\n        n += 1\n", max_steps=25)
        self.assertLess(time.monotonic() - start, 5)
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(out["frames"]), 25)
        self.assertIn("step", out["truncation_reason"])
        self.assertFalse(out["ok"])

    def test_blocking_call_has_time_limit_and_partial_frames(self):
        out = self.trace("import time\ndef f():\n    time.sleep(10)\n", timeout_ms=100)
        self.assertTrue(out["truncated"], out)
        self.assertEqual(out["exception"]["type"], "Timeout")
        self.assertTrue(out["frames"])

    def test_custom_objects_cycles_subclasses_and_nonfinite_are_safe(self):
        source = '''class Bad:
    def __repr__(self):
        raise RuntimeError("REPR HOOK RAN")
    def __str__(self):
        raise RuntimeError("STR HOOK RAN")
class BadList(list):
    def __iter__(self):
        raise RuntimeError("ITER HOOK RAN")
def f():
    obj = Bad()
    subclass = BadList([1, 2])
    recursive = []
    recursive.append(recursive)
    nan = float("nan")
    return {"ok": 1, "object": obj}
'''
        out = self.trace(source)
        self.assertTrue(out["ok"], out)
        encoded = json.dumps(out, allow_nan=False)
        self.assertIn("omitted", encoded)
        self.assertIn("cycle", encoded)
        self.assertNotIn("HOOK RAN", encoded)
        self.assertTrue(any("nan" in str(f["locals"]) for f in out["frames"]))

    def test_custom_exception_formatting_is_not_called(self):
        out = self.trace('class Bad(Exception):\n    def __str__(self):\n        raise RuntimeError("bad formatting")\ndef f():\n    raise Bad("safe message")\n')
        self.assertEqual(out["exception"]["type"], "Bad")
        self.assertEqual(out["exception"]["message"], "safe message")

    def test_stdout_and_large_snapshots_are_capped(self):
        out = self.trace('def f():\n    huge = list(range(10000))\n    print("x" * 20000)\n    return len(huge)\n')
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["output"], 10000)
        self.assertLessEqual(len(out["stdout"]), 4096)
        self.assertTrue(out["stdout_truncated"])
        self.assertLess(len(json.dumps(out)), 100000)
        self.assertTrue(any(f["stdout"] for f in out["frames"]))

    def test_class_operations_trace_real_methods(self):
        out = sandbox.trace_program("class Counter:\n    def __init__(self):\n        self.n = 0\n    def inc(self):\n        self.n += 1\n        return self.n\n",
            {"kind": "class_ops", "name": "Counter"}, {"ops": ["__init__", "inc", "inc"], "args": [[], [], []]})
        self.assertEqual(out["output"], [None, 1, 2])
        self.assertEqual(sum(f["event"] == "call" and f["function"] == "inc" for f in out["frames"]), 2)

    def test_refuses_hidden_or_oversized_input_before_launch(self):
        with patch.object(sandbox.subprocess, "Popen") as launch:
            for case in ({"hidden": True}, {"reveal": False}, {"args": ["x" * 70000]}):
                with self.assertRaises(ValueError):
                    sandbox.trace_program("def f(): pass", {"name": "f"}, case)
            with self.assertRaises(ValueError):
                self.trace("#" * 70000)
            launch.assert_not_called()

    def test_syntax_error_stays_inside_structured_result(self):
        out = self.trace("def f(:\n    pass\n")
        self.assertEqual(out["exception"]["type"], "SyntaxError")
        self.assertEqual(out["exception"]["line"], 1)
        self.assertEqual(out["frames"], [])

    def test_scrubbed_environment_and_network_containment(self):
        out = self.trace("import os, socket\ndef f():\n    home = os.path.expanduser('~')\n    try:\n        socket.create_connection(('1.1.1.1', 80), timeout=.2)\n        network = 'open'\n    except OSError:\n        network = 'blocked'\n    return [home, network]\n")
        self.assertTrue(out["ok"], out)
        self.assertNotEqual(out["output"][0], str(Path.home()))
        if out["hardened"]:
            self.assertEqual(out["output"][1], "blocked")


    def test_recursion_depth_and_snapshot_depth_are_bounded(self):
        out = self.trace("def f(n=0):\n    return f(n + 1)\n", max_steps=1000)
        self.assertTrue(out["truncated"])
        self.assertIn("depth", out["truncation_reason"])
        self.assertLessEqual(max(f["depth"] for f in out["frames"]), 48)
        nested = self.trace("def f():\n    x = [[[[[1]]]]]\n    return x\n", snapshot_depth=2)
        self.assertIn("depth limit", json.dumps(nested["output"]))

    def test_nested_exception_reports_original_player_line(self):
        out = self.trace("def broken():\n    return 1 / 0\ndef f():\n    return broken()\n")
        self.assertEqual(out["exception"]["line"], 2)

    def test_expected_answer_is_not_in_child_payload(self):
        # User Python can inspect its own process arguments; there must not be
        # an answer or grading rule in that payload even for a public example.
        out = sandbox.trace_program("import json, sys\ndef f():\n    return sorted(json.load(open(sys.argv[1]))['case'])\n",
            {"name": "f"}, {"name": "example", "args": [], "expected": "never shipped", "cmp": "exact"})
        self.assertEqual(out["output"], ["args"])

    def test_shared_launch_still_runs_ordinary_and_project_tests(self):
        out = sandbox.run_tests("def f(n):\n    return n * 2\n", {"name": "f"},
                                [{"name": "double", "args": [4], "expected": 8}])
        self.assertTrue(out.all_passed, out.to_dict())
        project = sandbox.run_project({"calc.py": "def double(n): return n * 2\n",
            "test_calc.py": "from calc import double\ndef test_double():\n    assert double(4) == 8\n"}, ["test_calc.py"])
        self.assertTrue(project.all_passed, project.to_dict())

    @unittest.skipIf(os.name == "nt", "POSIX alarm bypass test")
    def test_wall_limit_catches_disabled_trace_and_alarm(self):
        start = time.monotonic()
        out = self.trace("import signal, sys, time\ndef f():\n    sys.settrace(None)\n    signal.setitimer(signal.ITIMER_REAL, 0)\n    time.sleep(20)\n", wall_seconds=.25)
        self.assertLess(time.monotonic() - start, 3)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["exception"]["type"], "Timeout")


class TraceUITests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node is needed for the isolated UI contract check")
    def test_playback_navigation_visibility_and_teardown(self):
        script = r'''
import assert from 'node:assert/strict';
const timers = new Map(); let timerId = 0;
globalThis.setTimeout = fn => { timers.set(++timerId, fn); return timerId; };
globalThis.clearTimeout = id => timers.delete(id);
globalThis.fetch = () => { throw Error('Trace UI must not own networking'); };
class Node {
  constructor(tag) { this.tagName=tag; this.children=[]; this.listeners=new Map(); this.attrs={}; this.className=''; this.classes=new Set(); this.textContent=''; this.hidden=false; this.offsetTop=0; this.offsetHeight=26; this.clientHeight=300; this.scrollTop=0;
    this.classList={add:c=>this.classes.add(c), toggle:(c,v)=>{if(v)this.classes.add(c);else this.classes.delete(c);}};
  }
  get isConnected(){return this===document || !!this.parent?.isConnected;}
  append(...items){for(const child of items){child.parent=this;this.children.push(child);}}
  replaceChildren(...items){for(const c of this.children)c.parent=null;this.children=[];this.append(...items);}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);this.parent=null;}
  setAttribute(k,v){this.attrs[k]=v;} removeAttribute(k){delete this.attrs[k];}
  addEventListener(k,fn){if(!this.listeners.has(k))this.listeners.set(k,new Set());this.listeners.get(k).add(fn);}
  removeEventListener(k,fn){this.listeners.get(k)?.delete(fn);}
  emit(k){for(const fn of this.listeners.get(k)||[])fn({target:this});}
  getClientRects(){return this.isConnected?[{}]:[];}
  closest(){let node=this;while(node){if(node.hidden||node.attrs['aria-hidden']==='true')return node;node=node.parent;}return null;}
}
globalThis.document=new Node('document'); document.createElement=tag=>new Node(tag);
const host=new Node('div');host.ownerDocument=document;document.append(host);
const all=(node,match)=>[...(match(node)?[node]:[]),...node.children.flatMap(c=>all(c,match))];
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const {mount,changedLocals,describeFrame}=await import('./web/js/traceui.js');
assert.deepEqual(changedLocals({x:1,gone:2},{x:2,new:3}).map(x=>x.change),['changed','new','removed']);
assert.match(describeFrame({line:2,event:'line',function:'f',depth:0}),/before this line runs/);
assert.match(describeFrame({line:2,event:'yield',function:'f',value:null}),/yielded null; this call can resume/);
assert.match(describeFrame({line:2,event:'suspend',function:'f'}),/execution suspended/);
assert.match(describeFrame({line:2,event:'resume',function:'f'}),/resumed in the same call/);
assert.doesNotMatch(describeFrame({line:2,event:'resume',function:'f'}),/body has not run/);
assert.match(describeFrame({line:2,event:'unwind',function:'f'}),/exited because of an exception/);
const payload={source:'def f():\n    x = "<script>alert(1)</script>"\n    return x',case_label:'Visible example',ok:true,output:'safe',stdout:'printed',frames:[
  {line:1,event:'call',function:'f',call_id:1,locals:{},stdout:''},
  {line:2,event:'line',function:'f',call_id:1,locals:{x:1},stdout:''},
  {line:3,event:'return',function:'f',call_id:1,locals:{x:2},value:2,stdout:'printed'}]};
const ui=mount(host,payload),root=host.children[0];
const buttons=all(root,n=>n.tagName==='button');const [prev,play,next]=buttons;
const range=all(root,n=>n.tagName==='input')[0];
const caption=all(root,n=>n.className==='trace-caption')[0];
assert(prev.disabled);assert.equal(range.attrs['aria-label'],'Execution step');
next.emit('click');assert.equal(range.value,'1');assert.match(caption.textContent,/before this line runs/);
assert(all(root,n=>n.classes.has('current')).every(n=>n.attrs['aria-current']==='step'));
prev.emit('click');assert.equal(range.value,'0');
play.emit('click');assert.equal(play.textContent,'Pause');assert.equal(timers.size,1);
let fn=[...timers.values()][0];timers.clear();fn();assert.equal(range.value,'1');
document.hidden=true;document.emit('visibilitychange');assert.equal(timers.size,0);assert.equal(play.textContent,'Play');
document.hidden=false;play.emit('click');host.hidden=true;fn=[...timers.values()][0];timers.clear();fn();assert.equal(range.value,'1');assert.equal(play.textContent,'Play');host.hidden=false;
range.value='2';range.emit('input');assert(next.disabled);assert.match(caption.textContent,/returned 2/);
play.emit('click');assert.equal(range.value,'0','Play at the end restarts');
assert.equal(all(root,n=>n.tagName==='script').length,0,'Source stays text');
assert(text(root).includes('<script>alert(1)</script>'));
ui.destroy();ui.destroy();assert.equal(host.children.length,0);assert.equal(timers.size,0);
assert.equal(document.listeners.get('visibilitychange').size,0);
assert(buttons.every(b=>[...b.listeners.values()].every(v=>v.size===0)));
const suspended=mount(host,{source:'def f():\n    yield 1',frames:[
  {line:1,event:'call',function:'f',call_id:7,locals:{n:1}},
  {line:2,event:'yield',function:'f',call_id:7,locals:{n:1},value:1},
  {line:1,event:'call',function:'other',call_id:8,locals:{n:99}},
  {line:2,event:'resume',function:'f',call_id:7,locals:{n:1}},
  {line:2,event:'line',function:'f',call_id:7,locals:{n:2}}]});
const suspendedRange=all(host,n=>n.tagName==='input')[0];
suspendedRange.value='3';suspendedRange.emit('input');
assert.deepEqual(all(host,n=>n.className==='trace-change').map(n=>n.textContent),[''],'resume retains the same local comparison despite an interleaved call');
suspendedRange.value='4';suspendedRange.emit('input');
assert.deepEqual(all(host,n=>n.className==='trace-change').map(n=>n.textContent),['changed']);
suspended.destroy();
const empty=mount(host,{source:'bad python',frames:[],exception:{type:'SyntaxError',line:1,message:'bad syntax'}});
assert(text(host).includes('SyntaxError on line 1'));assert(all(host,n=>n.tagName==='button').every(b=>b.disabled));empty.destroy();
const limited=mount(host,{source:'while True: pass',frames:payload.frames,truncated:true,truncation_reason:'step limit',stdout_truncated:true});
assert(text(host).includes('Partial recording: step limit'));assert(text(host).includes('4,096'));limited.destroy();
console.log('trace UI: navigation, change labels, playback, hidden pause, safe source text, empty/error/truncated states, teardown verified');
'''
        result = subprocess.run([shutil.which("node"), "--input-type=module", "-e", script],
                                cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()
