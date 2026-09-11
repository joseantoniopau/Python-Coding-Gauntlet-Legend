"""Stack & Queue Mines. LIFO carts and FIFO lifts."""
from __future__ import annotations

from collections import deque

from ._base import code_problem

Q = {"QUORA": 2.5, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 1.0}
QS = {"QUORA": 1.0, "GENERAL_SWE": 1.0, "SECURITY_ENGINEERING": 3.0}
VIZ_S = {"type": "stack", "caption": "Objects pile up and come off the top."}
VIZ_Q = {"type": "queue", "caption": "First in the line is first out the door."}


def _valid_parens(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for ch in s:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack


def _eval_rpn(tokens):
    stack = []
    for tok in tokens:
        if tok in ("+", "-", "*", "/"):
            b = stack.pop()
            a = stack.pop()
            if tok == "+":
                stack.append(a + b)
            elif tok == "-":
                stack.append(a - b)
            elif tok == "*":
                stack.append(a * b)
            else:
                stack.append(int(a / b))
        else:
            stack.append(int(tok))
    return stack[-1] if stack else 0


def _daily_temperatures(temps):
    out = [0] * len(temps)
    stack = []
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            j = stack.pop()
            out[j] = i - j
        stack.append(i)
    return out


def _next_greater(nums):
    out = [-1] * len(nums)
    stack = []
    for i, v in enumerate(nums):
        while stack and nums[stack[-1]] < v:
            out[stack.pop()] = v
        stack.append(i)
    return out


def _simplify_path(path):
    parts = []
    for chunk in path.split("/"):
        if chunk in ("", "."):
            continue
        if chunk == "..":
            if parts:
                parts.pop()
        else:
            parts.append(chunk)
    return "/" + "/".join(parts)


def _decode_string(s):
    stack = [["", 1]]
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
        elif ch == "[":
            stack.append(["", int(digits or "1")])
            digits = ""
        elif ch == "]":
            text, times = stack.pop()
            stack[-1][0] += text * times
        else:
            stack[-1][0] += ch
    return stack[0][0]


def _remove_adjacent(s):
    stack = []
    for ch in s:
        if stack and stack[-1] == ch:
            stack.pop()
        else:
            stack.append(ch)
    return "".join(stack)


def _asteroid_collision(asteroids):
    stack = []
    for a in asteroids:
        alive = True
        while alive and a < 0 and stack and stack[-1] > 0:
            if stack[-1] < -a:
                stack.pop()
                continue
            if stack[-1] == -a:
                stack.pop()
            alive = False
        if alive:
            stack.append(a)
    return stack


def _moving_average(values, size):
    window, total, out = deque(), 0, []
    for v in values:
        window.append(v)
        total += v
        if len(window) > size:
            total -= window.popleft()
        out.append(total / len(window))
    return out


def _undo_remediation(actions):
    stack = []
    for op, target in actions:
        if op == "apply":
            stack.append(target)
        elif op == "undo" and stack:
            stack.pop()
    return stack


def _alert_triage(alerts, capacity):
    if capacity <= 0:
        return [[], len(alerts)]
    queue, dropped = deque(), 0
    for a in alerts:
        if len(queue) == capacity:
            queue.popleft()
            dropped += 1
        queue.append(a)
    return [list(queue), dropped]


def _backspace_compare(a, b):
    def build(text):
        stack = []
        for ch in text:
            if ch == "#":
                if stack:
                    stack.pop()
            else:
                stack.append(ch)
        return stack
    return build(a) == build(b)


def build() -> list:
    P: list = []

    P.append(code_problem(
        id="sq-valid-parens", title="The Balanced Vault", realm="stack_queue_mines",
        pattern="STACK", difficulty="EASY", family="stack_matching",
        profile_weight=Q, viz=VIZ_S, cmp="bool",
        statement="""
            Return `True` if every bracket in `s` is closed by the matching kind in the
            correct order. `s` contains only `()[]{}`.
        """,
        fn_name="is_valid", params="s", reference=_valid_parens,
        canonical="""
            def is_valid(s):
                closers = {")": "(", "]": "[", "}": "{"}
                stack = []
                for ch in s:
                    if ch in "([{":
                        stack.append(ch)
                    elif ch in closers:
                        if not stack or stack.pop() != closers[ch]:
                            return False
                return not stack
        """,
        visible=[("nested", ["([{}])"]), ("mismatched", ["(]"])],
        hidden=[("unclosed", ["((("]), ("extra closer", ["())"]),
                ("interleaved wrong", ["([)]"]), ("long valid", ["()[]{}" * 100])],
        edges=[("empty", [""]), ("single closer", [")"])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Counting brackets instead of matching them — '([)]' passes a counter",
                  "Forgetting to check the stack is empty at the end",
                  "Popping an empty stack"],
        nudge="The most recent unclosed bracket is the only one that can be closed next. "
              "That is the definition of a stack.",
        visual="Each opener drops onto a pile. Each closer must match whatever is on top, "
               "or the vault seals shut.",
        pseudocode="""
            for ch:
                opener -> push
                closer -> stack empty or pop() != match -> False
            return stack is empty
        """,
        tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="sq-eval-rpn", title="The Reverse Rite", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="stack_eval", profile_weight=Q,
        viz=VIZ_S,
        statement="""
            Evaluate an expression in reverse Polish notation. Tokens are integers or one
            of `+ - * /`. Division truncates toward zero.
        """,
        fn_name="eval_rpn", params="tokens", reference=_eval_rpn,
        canonical="""
            def eval_rpn(tokens):
                stack = []
                for tok in tokens:
                    if tok in ("+", "-", "*", "/"):
                        b = stack.pop()
                        a = stack.pop()          # order matters for - and /
                        if tok == "+":
                            stack.append(a + b)
                        elif tok == "-":
                            stack.append(a - b)
                        elif tok == "*":
                            stack.append(a * b)
                        else:
                            stack.append(int(a / b))   # truncate toward zero
                    else:
                        stack.append(int(tok))
                return stack[-1] if stack else 0
        """,
        visible=[("simple", [["2", "1", "+", "3", "*"]]),
                 ("division", [["4", "13", "5", "/", "+"]])],
        hidden=[("negatives", [["-3", "2", "*"]]),
                ("truncate toward zero", [["7", "-2", "/"]]),
                ("single value", [["42"]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Popping the operands in the wrong order breaks `-` and `/`",
                  "Using `//` which floors toward negative infinity, not toward zero"],
        nudge="Pop twice; the SECOND pop is the left operand.",
        visual="Values pile up; each operator eats the top two and pushes one back.",
        pseudocode="operand -> push; operator -> b=pop(), a=pop(), push(a op b)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sq-daily-temperatures", title="Waiting for Warmth", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="monotonic_stack",
        profile_weight=Q, viz={"type": "monotonic_stack",
                               "caption": "Only unresolved days wait on the pile."},
        statement="""
            For each day, report how many days you must wait for a strictly warmer
            temperature. Report `0` if no warmer day ever comes.
        """,
        fn_name="daily_temperatures", params="temps", reference=_daily_temperatures,
        canonical="""
            def daily_temperatures(temps):
                out = [0] * len(temps)
                stack = []                       # indices of days still waiting
                for i, t in enumerate(temps):
                    while stack and temps[stack[-1]] < t:
                        j = stack.pop()
                        out[j] = i - j
                    stack.append(i)
                return out
        """,
        visible=[("classic", [[73, 74, 75, 71, 69, 72, 76, 73]]),
                 ("never warmer", [[30, 20, 10]])],
        hidden=[("all equal", [[5, 5, 5]]), ("strictly rising", [[1, 2, 3]]),
                ("one dip", [[3, 1, 4]])],
        edges=[("empty", [[]]), ("single", [[50]])],
        perf=[("100k days", [[(i * 7919) % 100 for i in range(100000)]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Nested loops are O(n^2) and time out",
                  "Storing temperatures instead of indices, so you cannot compute the gap",
                  "Using `<=` and resolving equal days too early"],
        nudge="Days that are still waiting form a decreasing pile. A warm day resolves "
              "every colder day on top of it at once.",
        visual="Unresolved days stack up in decreasing order. A warmer day pops them all "
               "and stamps each with the distance.",
        pseudocode="""
            for i, t:
                while stack and temps[stack[-1]] < t:
                    j = stack.pop(); out[j] = i - j
                stack.append(i)
        """,
        variants=["sq-next-greater"], tags=["core", "quora"],
    ))

    P.append(code_problem(
        id="sq-next-greater", title="The Taller Neighbour", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="monotonic_stack",
        source_type="GENERATED_VARIANT", profile_weight=Q,
        statement="""
            For each value, return the first strictly greater value that appears later in
            the list, or `-1` if there is none.

            Same machine as Waiting for Warmth. Different thing stamped in the output.
        """,
        fn_name="next_greater", params="nums", reference=_next_greater,
        canonical="""
            def next_greater(nums):
                out = [-1] * len(nums)
                stack = []
                for i, value in enumerate(nums):
                    while stack and nums[stack[-1]] < value:
                        out[stack.pop()] = value
                    stack.append(i)
                return out
        """,
        visible=[("classic", [[2, 1, 2, 4, 3]]), ("descending", [[5, 4, 3]])],
        hidden=[("ascending", [[1, 2, 3]]), ("duplicates", [[2, 2, 3]]),
                ("negatives", [[-5, -1, -9]])],
        edges=[("empty", [[]]), ("single", [[1]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Stamping the index rather than the value"],
        nudge="Identical skeleton; you stamp the value, not the distance.",
        visual="A decreasing pile resolved by the next taller arrival.",
        pseudocode="while stack and nums[stack[-1]] < value: out[stack.pop()] = value",
        prerequisites=["sq-daily-temperatures"], tags=["variant"],
    ))

    P.append(code_problem(
        id="sq-simplify-path", title="The Winding Corridor", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="stack_matching",
        secondary=["STRING"], profile_weight=Q, viz=VIZ_S,
        statement="""
            Simplify an absolute Unix-style path. `.` means "stay", `..` means "go up one"
            (and does nothing at the root), and runs of slashes collapse. The result must
            start with `/` and must not end with one unless it is the root.
        """,
        fn_name="simplify_path", params="path", reference=_simplify_path,
        canonical="""
            def simplify_path(path):
                parts = []
                for chunk in path.split("/"):
                    if chunk in ("", "."):
                        continue
                    if chunk == "..":
                        if parts:
                            parts.pop()
                    else:
                        parts.append(chunk)
                return "/" + "/".join(parts)
        """,
        visible=[("trailing slash", ["/home/"]), ("up and up", ["/a/./b/../../c/"])],
        hidden=[("root parent", ["/../"]), ("double slash", ["/home//foo/"]),
                ("dotted name", ["/a/..."]), ("deep", ["/a/b/c/../../d"])],
        edges=[("root", ["/"]), ("all dots", ["/./././"])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Treating `...` as a special token — it is an ordinary directory name",
                  "Popping past the root",
                  "Leaving a trailing slash"],
        nudge="Split on '/', then let a stack absorb the navigation.",
        visual="Directories pile on; `..` lifts the top one off.",
        pseudocode="for chunk in path.split('/'): '' or '.' skip; '..' pop; else push",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sq-decode-string", title="The Nested Incantation", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="stack_nesting",
        secondary=["STRING", "RECURSION"], profile_weight=Q, viz=VIZ_S,
        statement="""
            Decode a string of the form `3[a2[c]]` into `accaccacc`. Repeat counts are
            positive integers and may have more than one digit. Brackets nest arbitrarily.
        """,
        fn_name="decode_string", params="s", reference=_decode_string,
        canonical="""
            def decode_string(s):
                stack = [["", 1]]          # (text so far, repeat count) frames
                digits = ""
                for ch in s:
                    if ch.isdigit():
                        digits += ch       # accumulate: counts can be multi-digit
                    elif ch == "[":
                        stack.append(["", int(digits or "1")])
                        digits = ""
                    elif ch == "]":
                        text, times = stack.pop()
                        stack[-1][0] += text * times
                    else:
                        stack[-1][0] += ch
                return stack[0][0]
        """,
        visible=[("simple", ["3[a]2[bc]"]), ("nested", ["3[a2[c]]"])],
        hidden=[("multi-digit", ["10[a]"]), ("mixed literal", ["2[abc]3[cd]ef"]),
                ("deep nesting", ["2[2[2[a]]]"])],
        edges=[("no brackets", ["abc"]), ("empty", [""])],
        time_complexity="O(output length)", space_complexity="O(depth)",
        failures=["Reading only one digit of a multi-digit count",
                  "Losing the text accumulated before the current bracket"],
        nudge="Every '[' opens a new frame. Every ']' folds that frame into its parent.",
        visual="Rooms inside rooms. You leave carrying the finished contents up a level.",
        pseudocode="""
            digit -> accumulate
            '['   -> push new frame with the count
            ']'   -> pop frame, append text*count to the frame below
            char  -> append to current frame
        """,
        tags=["core"],
    ))

    P.append(code_problem(
        id="sq-remove-adjacent", title="Annihilating Runes", realm="stack_queue_mines",
        pattern="STACK", difficulty="EASY", family="stack_matching",
        secondary=["STRING"], profile_weight=Q, viz=VIZ_S,
        statement="""
            Repeatedly remove any two adjacent identical characters until none remain.
            Return the resulting string. The result is unique regardless of removal order.
        """,
        fn_name="remove_adjacent_duplicates", params="s", reference=_remove_adjacent,
        canonical="""
            def remove_adjacent_duplicates(s):
                stack = []
                for ch in s:
                    if stack and stack[-1] == ch:
                        stack.pop()
                    else:
                        stack.append(ch)
                return "".join(stack)
        """,
        visible=[("classic", ["abbaca"]), ("cascade", ["azxxzy"])],
        hidden=[("all annihilate", ["aabb"]), ("none", ["abc"]), ("odd survivor", ["aaa"])],
        edges=[("empty", [""]), ("single", ["a"])],
        perf=[("200k chars", ["ab" * 100000])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Repeated string replacement is O(n^2) and misses cascades",
                  "Scanning again from the start after each removal"],
        nudge="A removal can expose a new pair. A stack handles the cascade for free.",
        visual="Each rune lands on the pile and annihilates with a matching top.",
        pseudocode="for ch: if stack top == ch: pop else push",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sq-backspace-compare", title="The Erased Message", realm="stack_queue_mines",
        pattern="STACK", difficulty="EASY", family="stack_matching",
        secondary=["STRING"], profile_weight=Q, viz=VIZ_S, cmp="bool",
        statement="""
            `#` means backspace. Return `True` if the two strings are equal after every
            backspace is applied. Backspacing an empty string does nothing.
        """,
        fn_name="backspace_compare", params="a, b", reference=_backspace_compare,
        canonical="""
            def backspace_compare(a, b):
                def build(text):
                    stack = []
                    for ch in text:
                        if ch == "#":
                            if stack:
                                stack.pop()
                        else:
                            stack.append(ch)
                    return stack

                return build(a) == build(b)
        """,
        visible=[("equal", ["ab#c", "ad#c"]), ("not equal", ["a#c", "b"])],
        hidden=[("both empty out", ["a##c", "#a#c"]), ("leading backspace", ["#ab", "ab"]),
                ("many backspaces", ["abc###", ""])],
        edges=[("both empty", ["", ""]), ("only backspaces", ["###", ""])],
        time_complexity="O(n + m)", space_complexity="O(n + m)",
        failures=["Popping an empty stack", "Comparing the raw strings"],
        nudge="Build both results, then compare once.",
        visual="Characters pile up; each '#' lifts one off.",
        pseudocode="build(text): push chars, pop on '#'; compare the two piles",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sq-asteroid-collision", title="Colliding Shards", realm="stack_queue_mines",
        pattern="STACK", difficulty="MEDIUM", family="stack_simulation",
        secondary=["SIMULATION"], profile_weight=Q, viz=VIZ_S,
        statement="""
            Each value is a shard: positive moves right, negative moves left, magnitude is
            size. A right-mover meeting a left-mover destroys the smaller; equal sizes
            destroy both. Shards moving the same way never meet.

            Return the surviving shards in order.
        """,
        fn_name="asteroid_collision", params="asteroids", reference=_asteroid_collision,
        canonical="""
            def asteroid_collision(asteroids):
                stack = []
                for shard in asteroids:
                    alive = True
                    # only a right-mover on the stack can collide with a left-mover
                    while alive and shard < 0 and stack and stack[-1] > 0:
                        if stack[-1] < -shard:
                            stack.pop()
                            continue
                        if stack[-1] == -shard:
                            stack.pop()
                        alive = False
                    if alive:
                        stack.append(shard)
                return stack
        """,
        visible=[("one dies", [[5, 10, -5]]), ("both die", [[8, -8]])],
        hidden=[("chain", [[10, 2, -5]]), ("no collisions", [[-2, -1, 1, 2]]),
                ("sweeps all", [[1, 2, 3, -10]]), ("all right", [[1, 2, 3]])],
        edges=[("empty", [[]]), ("single", [[-4]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Forgetting a surviving left-mover may destroy several stacked shards",
                  "Appending a shard that was destroyed",
                  "Colliding two shards moving the same direction"],
        nudge="Only a positive on top of the stack can be hit by an incoming negative.",
        visual="A right-moving pile; each left-mover carves into it until it stops or dies.",
        pseudocode="""
            for shard:
                while shard < 0 and stack and stack[-1] > 0: resolve collision
                if it survived: push
        """,
        tags=["core", "simulation"],
    ))

    P.append(code_problem(
        id="sq-moving-average", title="The Rolling Herald", realm="stack_queue_mines",
        pattern="QUEUE", difficulty="EASY", family="queue_window", profile_weight=Q,
        viz=VIZ_Q, cmp="float_list",
        statement="""
            Return the running average over the last `size` values, emitting one average
            per input value. Before the window is full, average what you have.
        """,
        fn_name="moving_averages", params="values, size", reference=_moving_average,
        canonical="""
            def moving_averages(values, size):
                from collections import deque
                window = deque()
                total = 0
                out = []
                for value in values:
                    window.append(value)
                    total += value
                    if len(window) > size:
                        total -= window.popleft()
                    out.append(total / len(window))
                return out
        """,
        visible=[("classic", [[1, 10, 3, 5], 3]), ("size one", [[4, 8], 1])],
        hidden=[("size exceeds input", [[1, 2], 10]), ("negatives", [[-2, 4], 2]),
                ("zeros", [[0, 0, 0], 2])],
        edges=[("empty", [[], 3])],
        perf=[("100k", [list(range(100000)), 500])],
        time_complexity="O(1) per value", space_complexity="O(size)",
        failures=["Re-summing the window each step", "Integer division",
                  "Dividing by `size` before the window is full"],
        nudge="A deque plus one running total. Divide by how many you actually hold.",
        visual="A line of values; the oldest leaves the front as a new one joins the back.",
        pseudocode="append, add; if too long popleft and subtract; emit total/len(window)",
        tags=["core"],
    ))

    P.append(code_problem(
        id="sec-undo-remediation", title="Rolling Back the Ward", realm="stack_queue_mines",
        pattern="STACK", difficulty="EASY", family="stack_simulation", security=True,
        profile_weight=QS, viz=VIZ_S,
        statement="""
            `actions` is a list of `[op, target]` where `op` is `"apply"` or `"undo"`.
            Applying pushes a remediation; undoing removes the most recent one. Undoing
            with nothing applied is a no-op.

            Return the remediations still in force, oldest first.
        """,
        fn_name="active_remediations", params="actions", reference=_undo_remediation,
        canonical="""
            def active_remediations(actions):
                stack = []
                for op, target in actions:
                    if op == "apply":
                        stack.append(target)
                    elif op == "undo" and stack:
                        stack.pop()
                return stack
        """,
        visible=[("apply and undo", [[["apply", "isolate-host"], ["apply", "block-ip"],
                                      ["undo", ""]]]),
                 ("all applied", [[["apply", "a"], ["apply", "b"]]])],
        hidden=[("undo empty", [[["undo", ""]]]),
                ("undo everything", [[["apply", "a"], ["undo", ""], ["undo", ""]]]),
                ("interleaved", [[["apply", "a"], ["undo", ""], ["apply", "b"]]])],
        edges=[("empty", [[]])],
        time_complexity="O(n)", space_complexity="O(n)",
        failures=["Popping an empty stack", "Removing the oldest instead of the newest"],
        nudge="Undo always targets the most recent action. That is a stack, by definition.",
        visual="Remediations pile up; undo lifts the top one off.",
        pseudocode="apply -> push; undo -> pop if non-empty",
        tags=["security", "transfer"],
    ))

    P.append(code_problem(
        id="sec-alert-queue", title="The Triage Line", realm="stack_queue_mines",
        pattern="QUEUE", difficulty="EASY", family="queue_window", security=True,
        profile_weight=QS, viz=VIZ_Q,
        statement="""
            Alerts arrive into a fixed-capacity buffer. When the buffer is full, the
            **oldest** alert is dropped to make room for the new one.

            Return `[remaining_alerts_oldest_first, dropped_count]`.
        """,
        fn_name="triage_buffer", params="alerts, capacity", reference=_alert_triage,
        canonical="""
            def triage_buffer(alerts, capacity):
                from collections import deque
                if capacity <= 0:
                    return [[], len(alerts)]     # nothing can ever be held
                queue = deque()
                dropped = 0
                for alert in alerts:
                    if len(queue) == capacity:
                        queue.popleft()
                        dropped += 1
                    queue.append(alert)
                return [list(queue), dropped]
        """,
        visible=[("overflow", [["a1", "a2", "a3", "a4"], 2]),
                 ("fits", [["a1", "a2"], 5])],
        hidden=[("capacity one", [["a", "b", "c"], 1]),
                ("exact fit", [["a", "b"], 2]),
                ("capacity zero", [["a"], 0])],
        edges=[("empty", [[], 3])],
        time_complexity="O(n)", space_complexity="O(capacity)",
        failures=["Using list.pop(0) is O(n) per drop",
                  "Dropping the newest alert instead of the oldest",
                  "Not handling capacity 0"],
        nudge="Oldest out is `popleft`, and only `deque` does that in O(1).",
        visual="A line at a gate; when full, the person at the front is turned away.",
        pseudocode="if full: popleft, dropped += 1; append",
        tags=["security", "transfer"],
    ))

    return P
