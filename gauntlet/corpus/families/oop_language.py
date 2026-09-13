"""Classes and exceptions as a LANGUAGE topic, not as a system-design topic.

`design_oop.py` already asks "build me a thing that remembers". This family asks
the other question, the one practical tests ask directly: do you know what
Python actually does when you write `class`, `super()`, `@property`, `__eq__` or
`try`. It is the missing half. Before this file the corpus could not teach a
single dunder method.

The rule this family is built on is the ramp, because the stated complaint about
this game was that it was too hard. Every topic below appears FIRST as a GUIDED
fill-in-the-blank — complete, working, readable code with exactly one hole in
it — then as TUTORIAL, where the structure is given and the bodies are not, then
as EASY, and only then harder. A topic whose first appearance is MEDIUM is a bug
in this file, not a challenge for the player.

The ladders, in the order the file builds them:

   1 class, __init__, methods          10 @property and its setter
   2 instance vs class attributes      11 @staticmethod vs @classmethod
   3 inheritance and super()           12 isinstance, type, ABCs, duck typing
   4 method resolution order           13 mutability and the default-argument trap
   5 __repr__ and __str__              14 try / except / else / finally
   6 __eq__ and __hash__               15 custom exceptions and `raise from`
   7 __len__ / __getitem__ / __contains__  16 catching narrowly
   8 __iter__ and exhaustion           17 __slots__
   9 __lt__ and ordering               18 the GIL, in plain language

Each rung names the rung below it as a prerequisite, so the order survives being
read by something other than a human scrolling this file.
"""
from __future__ import annotations

from ._base import code_problem, mcq_problem

# This player's declared profile. Language mechanics are asked in every one of
# these interviews, so the weighting is flat and high rather than pointed.
Q = {"PRACTICAL": 2.5, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 2.0}

VIZ = {"type": "object_state",
       "caption": "One object, its attributes, and who else can see them."}

VISUAL = {
    "GUIDED": "The class already works. Read it top to bottom, out loud if that "
              "helps, then fill the one hole. You are finishing a sentence, not "
              "writing an essay.",
    "TUTORIAL": "The structure is given. Write one method, run it, then write "
                "the next. Objects are easier to debug one attribute at a time.",
    "EASY": "Say what the object knows and what it can do, in English, before "
            "you type `class`. The typing is the cheap part.",
    "MEDIUM": "Trace it as the interpreter would: which class is looked at "
              "first, and what is bound to what at which moment.",
    "HARD": "Two mechanisms are interacting here. Name both before you change "
            "a line.",
}


def _same_move(body: str) -> str:
    """Rung 4 for a scaffolded problem. On a GUIDED fill-in-the-blank the first
    four lines of the solution ARE the answer, so showing them would make rung 4
    identical to Phoenix. This shows the same move on other data instead."""
    return "```python\n# the same move, somewhere else:\n" + body.strip() + "\n```"


def _oop(pid, title, statement, fn, params, ref, canonical, visible, hidden, *,
         difficulty="TUTORIAL", starter="", edges=(), pattern="SIMULATION",
         family="oop_classes", nudge="", visual="", pseudocode="", fragment="",
         failures=(), time="O(1)", space="O(1)", realm="fields_of_syntax",
         tags=(), after="", cmp="exact", secondary=()):
    """One rung. GUIDED rungs are MISSING_RUNE encounters: the game presents them
    as a hole in a working spell rather than as a fight with a blank screen."""
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        family=family, profile_weight=Q, viz=VIZ, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        secondary=list(secondary),
        time_complexity=time, space_complexity=space,
        failures=list(failures), nudge=nudge,
        visual=visual or VISUAL[difficulty],
        pseudocode=pseudocode, fragment=fragment,
        starter_code=starter,
        encounter="MISSING_RUNE" if difficulty == "GUIDED" else "CODE_BATTLE",
        prerequisites=[after] if after else [],
        tags=["python", "oop"] + list(tags),
    )


# ---------------------------------------------------------------------------
# Reference implementations
# ---------------------------------------------------------------------------
#
# Written without classes wherever a class is what the player must write. That
# is the point of the contract: the reference computes the expected answer by a
# different route, so a wrong canonical solution cannot quietly agree with it.

# 1 -- class, __init__, methods
def _ref_point_fields(x, y):
    return [x, y]


def _ref_running_totals(steps):
    out, total = [], 0
    for step in steps:
        total += step
        out.append(total)
    return out


def _ref_vault_log(start, moves):
    balance, out = start, []
    for move in moves:
        if move < 0 and balance + move < 0:
            out.append(balance)          # refused: the vault does not go negative
            continue
        balance += move
        out.append(balance)
    return out


# 2 -- instance vs class attributes
def _ref_count_instances(n):
    return n


def _ref_shadow(new_value):
    return [new_value, "unnamed", "unnamed"]


def _ref_pack_contents(first, second):
    return [list(first), list(second)]


# 3 -- inheritance and super()
def _ref_agent_fields(name, clearance):
    return [name, clearance]


def _ref_log_lines(texts):
    return ["[t] [log] " + text for text in texts]


def _ref_chain_parts(level):
    return {"base": ["base"],
            "middle": ["base", "middle"],
            "leaf": ["base", "middle", "leaf"]}[level]


# 4 -- method resolution order
def _ref_mro_names(which):
    return {"A": ["A", "object"],
            "B": ["B", "A", "object"],
            "C": ["C", "A", "object"],
            "D": ["D", "B", "C", "A", "object"]}[which]


def _ref_diamond_greeting(which):
    return {"root": "root", "left": "left", "right": "right", "both": "left"}[which]


def _ref_clean_text(text):
    return text.strip().lower()


# 5 -- __repr__ and __str__
def _ref_card_repr(rank, suit):
    return "Card(%r, %r)" % (rank, suit)


def _ref_temp_views(celsius):
    return ["%s degrees" % celsius, "Temp(%s)" % celsius, "[Temp(%s)]" % celsius]


def _ref_repr_roundtrip(x, y):
    return ["Vec(%r, %r)" % (x, y), True]


# 6 -- __eq__ and __hash__
def _ref_badges_equal(a, b):
    return a == b


def _ref_default_equality(value):
    return [False, True, True]


def _ref_unique_points(pairs):
    distinct = {(pair[0], pair[1]) for pair in pairs}
    return sorted([list(pair) for pair in distinct])


def _ref_hashability(kind):
    return {"plain": ["ok", 2],
            "eq_only": ["error", "TypeError"],
            "eq_and_hash": ["ok", 1]}[kind]


# 7 -- __len__ / __getitem__ / __contains__
def _ref_bag_size(items):
    return len(items)


def _ref_bag_at(items, index):
    return items[index]


def _ref_roster_report(names, probe):
    return [len(names), probe in names, list(names),
            names[-1] if names else None]


# 8 -- __iter__
def _ref_iterate_bag(items):
    return list(items)


def _ref_doubled(nums):
    return [n * 2 for n in nums]


def _ref_countdown_twice(start):
    first = []
    value = start
    while value > 0:
        first.append(value)
        value -= 1
    return [first, []]


# 9 -- __lt__ and ordering
def _ref_fastest_first(rows):
    return [row[0] for row in sorted(rows, key=lambda row: row[1])]


def _ref_fastest_with_tiebreak(rows):
    return [row[0] for row in sorted(rows, key=lambda row: (row[1], row[0]))]


def _ref_podium(rows):
    # min() and max() both keep the FIRST extreme they meet, which is not the
    # same as taking the ends of the sorted list when two scores tie.
    lowest, highest = rows[0], rows[0]
    for row in rows[1:]:
        if row[1] < lowest[1]:
            lowest = row
        if row[1] > highest[1]:
            highest = row
    ordered = sorted(rows, key=lambda row: row[1])
    return [lowest[0], highest[0], [row[0] for row in ordered]]


# 10 -- @property
def _ref_rect_area(width, height):
    return width * height


def _ref_temp_convert(celsius, target_f):
    return [celsius * 9 / 5 + 32, (target_f - 32) * 5 / 9]


def _ref_open_account(amount):
    if amount < 0:
        return ["error", "balance cannot be negative"]
    return ["ok", amount]


def _ref_freeze_report(width, height, new_area):
    return ["refused", width * height]


# 11 -- @staticmethod vs @classmethod
def _ref_shout(text):
    return text.upper()


def _ref_parse_date(text):
    return [int(part) for part in text.split("-")]


def _ref_method_kinds(value):
    return ["static:" + value, "Tool:" + value, "SubTool:" + value]


def _ref_constructor_kinds(size):
    return ["Square", "Shape", size]


# 12 -- isinstance, type, ABCs, duck typing
_TYPE_NAMES = {int: "int", bool: "bool", str: "str", float: "float",
               list: "list", dict: "dict", type(None): "NoneType"}


def _ref_type_names(values):
    return [_TYPE_NAMES[type(value)] for value in values]


def _ref_check_kinds(which):
    return {"animal": [True, True], "dog": [True, False]}[which]


def _ref_int_counts(values):
    strict = sum(1 for value in values if type(value) is int)
    flags = sum(1 for value in values if type(value) is bool)
    return [strict + flags, strict]


def _ref_export_report(which, rows):
    if which == "abstract":
        return ["error", "TypeError"]
    if which == "csv":
        return ["ok", ",".join(rows)]
    return ["ok", "|".join(rows)]


# 13 -- mutability
def _ref_collect(items):
    return [[item] for item in items]


def _ref_identity_report(values):
    return [True, False, True]


def _ref_copy_report(grid, value):
    # Only two distinct outcomes exist here: the rows that saw the write, and
    # the rows that were separated before it happened.
    written = [list(row) for row in grid]
    written[0][0] = value
    separated = [list(row) for row in grid]
    return [written, separated, written]


def _ref_default_trap(items):
    growing, shared = [], []
    for item in items:
        growing.append(item)
        shared.append(list(growing))
    return [shared, [[item] for item in items]]


# 14 -- try / except / else / finally
def _ref_safe_divide(a, b):
    if b == 0:
        return None
    return a / b


def _ref_classify_error(kind):
    return {"zero": "zero division", "key": "lookup", "index": "lookup",
            "type": "other", "clean": "none"}[kind]


def _ref_trace_blocks(kind):
    if kind == "boom":
        return ["try", "except", "finally", "after"]
    return ["try", "else", "finally", "after"]


def _ref_finally_report(kind):
    return {"plain": ["returned", "try"],
            "caught": ["returned", "except"],
            "swallowed": ["returned", "finally"],
            "escapes": ["raised", "TypeError"]}[kind]


# 15 -- custom exceptions
def _ref_load_setting(settings, key):
    if key in settings:
        return ["ok", settings[key]]
    return ["error", "missing setting: " + key]


def _ref_open_vault(state):
    return {"locked": ["vault", "LockedError"],
            "empty": ["vault", "EmptyError"],
            "cursed": ["other", "RuntimeError"],
            "open": ["ok", "open"]}[state]


def _ref_port_report(text):
    body = text[1:] if text[:1] in ("+", "-") else text
    if body.isdigit():
        value = int(body)
        return ["ok", -value if text[:1] == "-" else value]
    return ["error", "bad port: " + text, "ValueError"]


# 16 -- catching narrowly
def _ref_parse_all(values):
    out = []
    for value in values:
        if isinstance(value, bool):
            out.append(int(value))
        elif isinstance(value, (int, float)):
            out.append(int(value))
        elif isinstance(value, str) and value.strip().lstrip("+-").isdigit():
            out.append(int(value))
        else:
            out.append(None)
    return out


def _ref_guard_report(kind):
    if kind == "value":
        return ["returned", "caught"]
    if kind == "exit":
        return ["escaped", "SystemExit"]
    return ["returned", "clean"]


def _ref_audit(source, key):
    if key in source:
        return ["ok", source[key], []]
    return ["error", "KeyError", ["missing:" + key]]


# 17 -- __slots__
def _ref_pixel_fields(x, y):
    return [x, y, ["x", "y"]]


def _ref_slots_report(name):
    return ["assigned" if name in ("x", "y") else "refused", name]


def _ref_dict_report(which):
    return {"plain": [True, 1], "slotted": [False, 1], "child": [True, 1]}[which]


# 18 -- the GIL
def _ref_pick_executor(workload):
    return "processes" if workload == "cpu" else "threads"


def _ref_locked_total(threads, per_thread):
    return threads * per_thread


def build() -> list:
    return [
        # ==================================================================
        # 1. class, __init__, methods
        # ==================================================================
        _oop(
            "oopl-init-guided", "A Thing With Two Names",
            """
            A class is a template. `__init__` runs once per object and its job is
            to hang values off `self` so the object remembers them.

            `Point` is written for you and one attribute is missing. Store `y` on
            the object the same way `x` is stored.
            """,
            "point_fields", "x, y", _ref_point_fields,
            """
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y


            def point_fields(x, y):
                point = Point(x, y)
                return [point.x, point.y]
            """,
            [("origin", [0, 0]), ("positive", [3, 4])],
            [("negative", [-2, 7]), ("large", [1000, -1000])],
            edges=[("one axis zero", [0, 5])],
            difficulty="GUIDED", family="oop_classes",
            starter="""
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    # `self` is this particular Point. Give it a `y` as well.
                    self.y = __BLANK__


            def point_fields(x, y):
                point = Point(x, y)
                return [point.x, point.y]
            """,
            nudge="`self.x = x` does not compare anything. It means 'this object's "
                  "x is, from now on, that value'.",
            pseudocode="self.y = the y that was passed in",
            fragment=_same_move("self.label = label"),
            failures=["Writing `y = y`, which assigns a local nobody will ever read",
                      "Forgetting `self.` and wondering where the attribute went"],
            tags=["class", "init"],
        ),

        _oop(
            "oopl-method-tutorial", "The Tally That Remembers",
            """
            A method is a function that lives on the class and receives the object
            as its first argument, spelled `self` by convention.

            Write `Tally`: it starts at zero, and `add(amount)` increases the
            running total and returns the new total. `run_counter` then returns
            the total after each step.
            """,
            "run_counter", "steps", _ref_running_totals,
            """
            class Tally:
                def __init__(self):
                    self.total = 0

                def add(self, amount):
                    self.total += amount
                    return self.total


            def run_counter(steps):
                tally = Tally()
                return [tally.add(step) for step in steps]
            """,
            [("counting up", [[1, 2, 3]]), ("with a drop", [[5, -2, 1]])],
            [("all zeros", [[0, 0]]), ("single", [[7]]), ("negatives", [[-1, -1, -1]])],
            edges=[("no steps", [[]])],
            difficulty="TUTORIAL", family="oop_classes", after="oopl-init-guided",
            starter="""
            class Tally:
                def __init__(self):
                    # one attribute: the running total, starting at zero
                    pass

                def add(self, amount):
                    # add to the total, then hand the new total back
                    pass


            def run_counter(steps):
                tally = Tally()
                # call tally.add once per step and collect what it returns
                pass
            """,
            nudge="The object is the memory. Nothing between calls to `add` has to "
                  "carry the total for you.",
            pseudocode="class Tally:\n  __init__: self.total = 0\n  add(amount): "
                       "self.total += amount; return self.total",
            failures=["Returning `amount` instead of the new total",
                      "Creating a fresh Tally inside the loop, which forgets everything"],
            tags=["class", "method"],
        ),

        _oop(
            "oopl-state-easy", "The Vault That Says No",
            """
            Write a `Vault` class that holds a balance and applies a list of moves.
            A positive move is a deposit. A negative move is a withdrawal, and a
            withdrawal that would take the balance below zero is refused outright
            — the balance simply does not change.

            `vault_log(start, moves)` returns the balance after each move,
            including the unchanged balance for a refused one.
            """,
            "vault_log", "start, moves", _ref_vault_log,
            """
            class Vault:
                def __init__(self, balance):
                    self.balance = balance

                def apply(self, move):
                    # A refused withdrawal is not an error here, it is a no-op.
                    if move < 0 and self.balance + move < 0:
                        return self.balance
                    self.balance += move
                    return self.balance


            def vault_log(start, moves):
                vault = Vault(start)
                return [vault.apply(move) for move in moves]
            """,
            [("deposits", [10, [5, 5]]), ("one refusal", [10, [-4, -20, 1]])],
            [("exact zero is allowed", [5, [-5]]), ("all refused", [0, [-1, -2]]),
             ("mixed", [3, [7, -10, -1]])],
            edges=[("no moves", [0, []]), ("start at zero", [0, [-1, 4]])],
            difficulty="EASY", family="oop_classes", after="oopl-method-tutorial",
            starter="""
            class Vault:
                def __init__(self, balance):
                    pass

                def apply(self, move):
                    pass


            def vault_log(start, moves):
                pass
            """,
            nudge="Decide the refusal rule before you touch `self.balance`. Once "
                  "you have mutated it, you cannot un-mutate it cleanly.",
            pseudocode="if move < 0 and balance + move < 0: return balance unchanged\n"
                       "otherwise balance += move and return it",
            failures=["Clamping to zero instead of refusing, which loses the deposit",
                      "Refusing a withdrawal that lands exactly on zero"],
            time="O(n)", tags=["class", "state"],
        ),

        # ==================================================================
        # 2. instance attributes vs class attributes
        # ==================================================================
        _oop(
            "oopl-classattr-guided", "One Counter For All Of Them",
            """
            An attribute written inside the class body, not inside `__init__`,
            belongs to the CLASS. Every instance sees the same one.

            `Golem.made` is such an attribute. Fill in the line in `__init__` that
            increases it, so the class counts how many golems exist.
            """,
            "count_instances", "n", _ref_count_instances,
            """
            class Golem:
                made = 0            # lives on the class, shared by every instance

                def __init__(self):
                    Golem.made += 1


            def count_instances(n):
                # Reset first: the class attribute outlives every Golem.
                Golem.made = 0
                for _ in range(n):
                    Golem()
                return Golem.made
            """,
            [("three", [3]), ("one", [1])],
            [("ten", [10]), ("two", [2]), ("fifty", [50])],
            edges=[("none at all", [0])],
            difficulty="GUIDED", family="oop_class_attrs", after="oopl-state-easy",
            starter="""
            class Golem:
                made = 0            # lives on the class, shared by every instance

                def __init__(self):
                    # Count this golem. Name the class, not `self`.
                    __BLANK__


            def count_instances(n):
                # Reset first: the class attribute outlives every Golem.
                Golem.made = 0
                for _ in range(n):
                    Golem()
                return Golem.made
            """,
            nudge="`self.made += 1` would read the class value once and then write "
                  "a brand new INSTANCE attribute. Write to the class by name.",
            pseudocode="Golem.made = Golem.made + 1",
            fragment=_same_move("Session.opened += 1"),
            failures=["`self.made += 1`, which silently shadows instead of counting",
                      "Putting `made = 0` inside __init__, which resets it every time"],
            tags=["class-attribute"],
        ),

        _oop(
            "oopl-classattr-tutorial", "The Shadow On The Instance",
            """
            Assigning to `instance.attr` never changes the class attribute. It
            creates an instance attribute that hides it, for that one object only.

            `Sigil.tag` starts as "unnamed". Set `new_value` on ONE instance, then
            return `[a.tag, b.tag, Sigil.tag]` so the shadowing is visible.
            """,
            "shadow_demo", "new_value", _ref_shadow,
            """
            class Sigil:
                tag = "unnamed"


            def shadow_demo(new_value):
                a = Sigil()
                b = Sigil()
                # This does NOT touch Sigil.tag. It gives `a` a tag of its own.
                a.tag = new_value
                return [a.tag, b.tag, Sigil.tag]
            """,
            [("named", ["warded"]), ("short", ["x"])],
            [("spaces", ["old sigil"]), ("digits", ["7"]), ("empty", [""])],
            edges=[("same as default", ["unnamed"])],
            difficulty="TUTORIAL", family="oop_class_attrs",
            after="oopl-classattr-guided",
            starter="""
            class Sigil:
                tag = "unnamed"


            def shadow_demo(new_value):
                a = Sigil()
                b = Sigil()
                # give `a` its own tag, then report all three
                pass
            """,
            nudge="Reading an attribute falls back to the class. Writing one never "
                  "does.",
            pseudocode="a.tag = new_value\nreturn [a.tag, b.tag, Sigil.tag]",
            failures=["Expecting `b.tag` to change too",
                      "Assigning `Sigil.tag`, which changes it for everyone"],
            tags=["class-attribute", "shadowing"],
        ),

        _oop(
            "oopl-classattr-easy", "The List They All Share",
            """
            A mutable class attribute is the same trap wearing a costume. Every
            instance appends to the SAME list, and nobody notices until two
            objects are in play.

            Write `Pack` so each pack has its own `contents`. `pack_contents`
            fills two packs and returns `[first_pack.contents, second_pack.contents]`.
            """,
            "pack_contents", "first, second", _ref_pack_contents,
            """
            class Pack:
                def __init__(self):
                    # Per instance, created fresh in __init__. A `contents = []`
                    # in the class body would be one list shared by every Pack.
                    self.contents = []

                def add(self, item):
                    self.contents.append(item)
                    return self.contents


            def pack_contents(first, second):
                a, b = Pack(), Pack()
                for item in first:
                    a.add(item)
                for item in second:
                    b.add(item)
                return [a.contents, b.contents]
            """,
            [("two packs", [["rope"], ["torch", "flint"]]),
             ("one empty", [[], ["map"]])],
            [("same items", [["a"], ["a"]]), ("longer", [["a", "b", "c"], ["d"]]),
             ("numbers", [[1, 2], [3]])],
            edges=[("both empty", [[], []])],
            difficulty="EASY", family="oop_class_attrs",
            after="oopl-classattr-tutorial",
            starter="""
            class Pack:
                def __init__(self):
                    pass

                def add(self, item):
                    pass


            def pack_contents(first, second):
                pass
            """,
            nudge="If the list is created in the class body it is created once, "
                  "when the class is defined. You want one per object.",
            pseudocode="__init__: self.contents = []\nadd: self.contents.append(item)",
            failures=["`contents = []` in the class body — both packs end up holding "
                      "everything",
                      "Reassigning `self.contents = self.contents + [item]`, which "
                      "works but quietly drops any alias someone else held"],
            time="O(n)", tags=["class-attribute", "mutable"],
        ),

        # ==================================================================
        # 3. inheritance and super()
        # ==================================================================
        _oop(
            "oopl-super-guided", "Let The Parent Go First",
            """
            A subclass that writes its own `__init__` replaces the parent's. If
            you still want the parent's setup to happen, you have to ask for it:
            `super().__init__(...)`.

            `Admin` forgets to. Add the call so `name` gets stored.
            """,
            "describe_agent", "name, clearance", _ref_agent_fields,
            """
            class User:
                def __init__(self, name):
                    self.name = name


            class Admin(User):
                def __init__(self, name, clearance):
                    super().__init__(name)
                    self.clearance = clearance


            def describe_agent(name, clearance):
                admin = Admin(name, clearance)
                return [admin.name, admin.clearance]
            """,
            [("root", ["root", 9]), ("analyst", ["ada", 2])],
            [("zero clearance", ["guest", 0]), ("long name", ["administrator", 5]),
             ("numeric name", ["7", 1])],
            edges=[("empty name", ["", 0])],
            difficulty="GUIDED", family="oop_inheritance", after="oopl-classattr-easy",
            starter="""
            class User:
                def __init__(self, name):
                    self.name = name


            class Admin(User):
                def __init__(self, name, clearance):
                    # Run User.__init__ so `name` actually gets stored.
                    __BLANK__
                    self.clearance = clearance


            def describe_agent(name, clearance):
                admin = Admin(name, clearance)
                return [admin.name, admin.clearance]
            """,
            nudge="`super()` with no arguments means 'the next class after this one "
                  "in the lookup order'. You still have to pass the parent's own "
                  "arguments to it.",
            pseudocode="super().__init__(name)",
            fragment=_same_move("super().__init__(host, port)"),
            failures=["Calling `User.__init__(name)` and getting a missing-argument "
                      "error, because `self` is not passed automatically that way",
                      "Setting `self.name = name` by hand, which works today and "
                      "breaks the day the parent's setup grows"],
            tags=["inheritance", "super"],
        ),

        _oop(
            "oopl-super-override-tutorial", "Extending, Not Replacing",
            """
            Overriding a method usually means "do what the parent did, then do one
            more thing". `super().method(...)` is how you get the parent's answer
            without copying its body.

            Write `TimestampLogger.line` so it returns the parent's line with
            `"[t] "` in front.
            """,
            "log_lines", "texts", _ref_log_lines,
            """
            class Logger:
                def line(self, text):
                    return "[log] " + text


            class TimestampLogger(Logger):
                def line(self, text):
                    return "[t] " + super().line(text)


            def log_lines(texts):
                logger = TimestampLogger()
                return [logger.line(text) for text in texts]
            """,
            [("two lines", [["boot", "ready"]]), ("one line", [["halt"]])],
            [("empty string", [[""]]), ("spaces", [["a b"]]),
             ("many", [["a", "b", "c", "d"]])],
            edges=[("no lines", [[]])],
            difficulty="TUTORIAL", family="oop_inheritance", after="oopl-super-guided",
            starter="""
            class Logger:
                def line(self, text):
                    return "[log] " + text


            class TimestampLogger(Logger):
                def line(self, text):
                    # call the parent's version, then decorate what it returned
                    pass


            def log_lines(texts):
                logger = TimestampLogger()
                return [logger.line(text) for text in texts]
            """,
            nudge="Copying `\"[log] \" + text` into the child would pass this test "
                  "and rot the first time Logger changes.",
            pseudocode='return "[t] " + super().line(text)',
            failures=["`self.line(text)`, which calls the child again — infinite "
                      "recursion"],
            time="O(n)", tags=["inheritance", "super", "override"],
        ),

        _oop(
            "oopl-super-chain-easy", "Three Deep",
            """
            `super()` chains. Each level adds its own piece and asks the level
            above for the rest, so a three-deep hierarchy builds its answer from
            the root down.

            Write `Base`, `Middle(Base)` and `Leaf(Middle)`, each with a `parts()`
            method. `chain_parts(level)` builds the class named by `level` and
            returns its parts, root first.
            """,
            "chain_parts", "level", _ref_chain_parts,
            """
            class Base:
                def parts(self):
                    return ["base"]


            class Middle(Base):
                def parts(self):
                    return super().parts() + ["middle"]


            class Leaf(Middle):
                def parts(self):
                    return super().parts() + ["leaf"]


            def chain_parts(level):
                chosen = {"base": Base, "middle": Middle, "leaf": Leaf}[level]
                return chosen().parts()
            """,
            [("leaf", ["leaf"]), ("base", ["base"])],
            [("middle", ["middle"]), ("leaf again", ["leaf"]), ("base again", ["base"])],
            edges=[("middle only", ["middle"])],
            difficulty="EASY", family="oop_inheritance",
            after="oopl-super-override-tutorial",
            starter="""
            class Base:
                def parts(self):
                    pass


            class Middle(Base):
                def parts(self):
                    pass


            class Leaf(Middle):
                def parts(self):
                    pass


            def chain_parts(level):
                chosen = {"base": Base, "middle": Middle, "leaf": Leaf}[level]
                return chosen().parts()
            """,
            nudge="Put the super() call FIRST in the concatenation and the list "
                  "comes out root first, for free.",
            pseudocode="Base.parts -> ['base']\nMiddle.parts -> super() + ['middle']\n"
                       "Leaf.parts -> super() + ['leaf']",
            failures=["Returning `['leaf'] + super().parts()`, which reverses the order",
                      "Hardcoding the full list in Leaf, which stops being true the "
                      "moment Middle changes"],
            tags=["inheritance", "super"],
        ),

        # ==================================================================
        # 4. method resolution order
        # ==================================================================
        _oop(
            "oopl-mro-guided", "The Order Of Looking",
            """
            When you ask an object for an attribute, Python walks a fixed list of
            classes and takes the first hit. That list is the method resolution
            order, and every class carries it as `__mro__`.

            Return the class NAMES of the chosen class's MRO.
            """,
            "mro_names", "which", _ref_mro_names,
            """
            class A:
                pass


            class B(A):
                pass


            class C(A):
                pass


            class D(B, C):
                pass


            def mro_names(which):
                chosen = {"A": A, "B": B, "C": C, "D": D}[which]
                return [cls.__name__ for cls in chosen.__mro__]
            """,
            [("the diamond", ["D"]), ("a leaf", ["B"])],
            [("the other leaf", ["C"]), ("the root", ["A"]), ("diamond again", ["D"])],
            edges=[("root only", ["A"])],
            difficulty="GUIDED", family="oop_mro", after="oopl-super-chain-easy",
            starter="""
            class A:
                pass


            class B(A):
                pass


            class C(A):
                pass


            class D(B, C):
                pass


            def mro_names(which):
                chosen = {"A": A, "B": B, "C": C, "D": D}[which]
                # Every class carries its lookup order. Walk it and take the names.
                return [cls.__name__ for cls in __BLANK__]
            """,
            nudge="`object` is on the end of every MRO, because every class "
                  "inherits from it whether you said so or not.",
            pseudocode="for cls in chosen.__mro__: collect cls.__name__",
            fragment=_same_move("print(type(value).__mro__)"),
            failures=["Expecting D's order to be D, B, A, C, object — Python visits "
                      "C before it visits their shared parent A"],
            tags=["mro", "inheritance"],
        ),

        _oop(
            "oopl-mro-resolve-tutorial", "Which Parent Wins",
            """
            `Both` inherits from `Left` and `Right`, and both of them define
            `greet`. Exactly one of them wins, and the MRO decides which.

            Write `greeting_for(which)`: build the named class, call `greet`, and
            return what it said.
            """,
            "diamond_greeting", "which", _ref_diamond_greeting,
            """
            class Root:
                def greet(self):
                    return "root"


            class Left(Root):
                def greet(self):
                    return "left"


            class Right(Root):
                def greet(self):
                    return "right"


            class Both(Left, Right):
                pass


            def diamond_greeting(which):
                chosen = {"root": Root, "left": Left,
                          "right": Right, "both": Both}[which]
                return chosen().greet()
            """,
            [("the diamond", ["both"]), ("the root", ["root"])],
            [("left", ["left"]), ("right", ["right"]), ("diamond again", ["both"])],
            edges=[("right only", ["right"])],
            difficulty="TUTORIAL", family="oop_mro", after="oopl-mro-guided",
            starter="""
            class Root:
                def greet(self):
                    return "root"


            class Left(Root):
                def greet(self):
                    return "left"


            class Right(Root):
                def greet(self):
                    return "right"


            class Both(Left, Right):
                pass


            def diamond_greeting(which):
                # look the class up, build one, ask it to greet
                pass
            """,
            nudge="Base classes are searched left to right. `Both(Left, Right)` "
                  "means Left is asked first.",
            pseudocode="chosen = table[which]\nreturn chosen().greet()",
            failures=["Assuming the last base listed wins",
                      "Assuming ambiguity is an error — it is not, it is an order"],
            tags=["mro", "inheritance"],
        ),

        _oop(
            "oopl-mro-cooperative-easy", "A Pipeline Made Of Parents",
            """
            Because every class in the MRO can call `super()`, multiple inheritance
            can be used as a pipeline: each class does its bit and passes the value
            along the chain.

            Write `Trim` and `Lower` so that `Clean(Trim, Lower)` strips whitespace
            and then lowercases. Neither class may call the other by name.
            """,
            "clean_text", "text", _ref_clean_text,
            """
            class Pipeline:
                def run(self, data):
                    return data


            class Trim(Pipeline):
                def run(self, data):
                    return super().run(data.strip())


            class Lower(Pipeline):
                def run(self, data):
                    return super().run(data.lower())


            class Clean(Trim, Lower):
                pass


            def clean_text(text):
                # MRO: Clean -> Trim -> Lower -> Pipeline. Each link runs once.
                return Clean().run(text)
            """,
            [("padded shout", ["  HELLO  "]), ("already clean", ["ok"])],
            [("tabs", ["\tMixed Case\t"]), ("inner spaces kept", ["  A B  "]),
             ("digits", [" 42 "])],
            edges=[("empty", [""]), ("only spaces", ["   "])],
            difficulty="EASY", family="oop_mro", after="oopl-mro-resolve-tutorial",
            starter="""
            class Pipeline:
                def run(self, data):
                    return data


            class Trim(Pipeline):
                def run(self, data):
                    # strip, then hand it to whoever is next in the MRO
                    pass


            class Lower(Pipeline):
                def run(self, data):
                    pass


            class Clean(Trim, Lower):
                pass


            def clean_text(text):
                return Clean().run(text)
            """,
            nudge="`super()` inside Trim does not mean Pipeline. It means 'the next "
                  "class after Trim in the MRO of the object I am actually on', "
                  "which for a Clean instance is Lower.",
            pseudocode="Trim.run: super().run(data.strip())\n"
                       "Lower.run: super().run(data.lower())\n"
                       "Pipeline.run: return data",
            failures=["Calling `Pipeline.run(self, data)` directly, which skips Lower "
                      "entirely",
                      "Forgetting the super() call in one link, which silently drops "
                      "the rest of the pipeline"],
            time="O(n)", tags=["mro", "super", "mixin"],
        ),

        # ==================================================================
        # 5. __repr__ and __str__
        # ==================================================================
        _oop(
            "oopl-repr-guided", "Saying What You Are",
            """
            `__repr__` is what an object says when it is printed in a list, shown
            in a debugger, or echoed at a prompt. The convention is: return
            something that looks like the call that would rebuild it.

            Fill in the returned string so `Card("A", "spades")` reprs as
            `Card('A', 'spades')`.
            """,
            "card_repr", "rank, suit", _ref_card_repr,
            """
            class Card:
                def __init__(self, rank, suit):
                    self.rank = rank
                    self.suit = suit

                def __repr__(self):
                    # !r applies repr() to the field, which is what puts the
                    # quotes on a string and leaves a number bare.
                    return f"Card({self.rank!r}, {self.suit!r})"


            def card_repr(rank, suit):
                return repr(Card(rank, suit))
            """,
            [("ace", ["A", "spades"]), ("number card", ["10", "hearts"])],
            [("apostrophe", ["K", "o'clock"]), ("empty suit", ["Q", ""]),
             ("single letters", ["2", "c"])],
            edges=[("both empty", ["", ""])],
            difficulty="GUIDED", family="oop_repr", after="oopl-mro-cooperative-easy",
            starter="""
            class Card:
                def __init__(self, rank, suit):
                    self.rank = rank
                    self.suit = suit

                def __repr__(self):
                    # `!r` inside an f-string means "use repr() on this field".
                    return __BLANK__


            def card_repr(rank, suit):
                return repr(Card(rank, suit))
            """,
            nudge="Without `!r` you get Card(A, spades), which is not a thing you "
                  "could paste back into Python.",
            pseudocode='return f"Card({self.rank!r}, {self.suit!r})"',
            fragment=_same_move('return f"User({self.name!r})"'),
            failures=["Using `str()` semantics and losing the quotes",
                      "Printing inside __repr__ instead of returning"],
            pattern="STRING", tags=["dunder", "repr"],
        ),

        _oop(
            "oopl-repr-vs-str-tutorial", "Two Different Audiences",
            """
            `__str__` is for a human reading output. `__repr__` is for a developer
            reading a traceback. `print(x)` uses `__str__`; putting `x` inside a
            list and printing the list uses `__repr__`, because containers repr
            their contents.

            Give `Temp` both, then return `[str(t), repr(t), repr([t])]`.
            """,
            "temp_views", "celsius", _ref_temp_views,
            """
            class Temp:
                def __init__(self, celsius):
                    self.celsius = celsius

                def __str__(self):
                    return f"{self.celsius} degrees"

                def __repr__(self):
                    return f"Temp({self.celsius})"


            def temp_views(celsius):
                reading = Temp(celsius)
                # The list does not call __str__ on its elements. It never does.
                return [str(reading), repr(reading), repr([reading])]
            """,
            [("room", [21]), ("freezing", [0])],
            [("negative", [-40]), ("hot", [100]), ("large", [1000])],
            edges=[("below zero", [-1])],
            difficulty="TUTORIAL", family="oop_repr", after="oopl-repr-guided",
            starter="""
            class Temp:
                def __init__(self, celsius):
                    self.celsius = celsius

                def __str__(self):
                    # what a person reads: "21 degrees"
                    pass

                def __repr__(self):
                    # what a developer reads: "Temp(21)"
                    pass


            def temp_views(celsius):
                reading = Temp(celsius)
                pass
            """,
            nudge="If you define only `__repr__`, `str()` falls back to it. The "
                  "reverse is not true.",
            pseudocode='__str__ -> "<c> degrees"\n__repr__ -> "Temp(<c>)"\n'
                       "return [str(t), repr(t), repr([t])]",
            failures=["Expecting a list of Temps to print the friendly form"],
            pattern="STRING", tags=["dunder", "repr", "str"],
        ),

        _oop(
            "oopl-repr-roundtrip-easy", "A Repr You Could Paste Back",
            """
            The strongest form of `__repr__` is one that evaluates back into an
            equal object. It costs nothing extra and it makes every log line a
            reproducible test case.

            Write `Vec` with such a `__repr__`. `repr_roundtrip` returns the repr
            text and whether rebuilding from it restores both fields.
            """,
            "repr_roundtrip", "x, y", _ref_repr_roundtrip,
            """
            class Vec:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def __repr__(self):
                    return f"Vec({self.x!r}, {self.y!r})"


            def repr_roundtrip(x, y):
                original = Vec(x, y)
                # eval is a terrible habit in production and a fine proof here.
                clone = eval(repr(original), {"Vec": Vec})
                return [repr(original), clone.x == x and clone.y == y]
            """,
            [("integers", [1, 2]), ("negatives", [-3, -4])],
            [("zero", [0, 0]), ("large", [10 ** 6, 7]), ("mixed sign", [-1, 5])],
            edges=[("both zero", [0, 0])],
            difficulty="EASY", family="oop_repr", after="oopl-repr-vs-str-tutorial",
            starter="""
            class Vec:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def __repr__(self):
                    pass


            def repr_roundtrip(x, y):
                original = Vec(x, y)
                clone = eval(repr(original), {"Vec": Vec})
                return [repr(original), clone.x == x and clone.y == y]
            """,
            nudge="The class name in the repr has to match the name the reader can "
                  "actually call. Hardcoding the wrong one is the classic bug here.",
            pseudocode='return f"Vec({self.x!r}, {self.y!r})"',
            failures=["Using `<Vec x=1 y=2>` angle-bracket style, which reads well "
                      "and cannot be rebuilt"],
            pattern="STRING", tags=["dunder", "repr"],
        ),

        # ==================================================================
        # 6. __eq__ and __hash__
        # ==================================================================
        _oop(
            "oopl-eq-guided", "Equal By Value",
            """
            By default two objects are equal only if they are the same object.
            `__eq__` lets you say what equality actually means for your type.

            Two badges are equal when their numbers match. Fill in the comparison.
            """,
            "badges_equal", "a, b", _ref_badges_equal,
            """
            class Badge:
                def __init__(self, number):
                    self.number = number

                def __eq__(self, other):
                    if not isinstance(other, Badge):
                        return NotImplemented
                    return self.number == other.number


            def badges_equal(a, b):
                return Badge(a) == Badge(b)
            """,
            [("same", [7, 7]), ("different", [7, 8])],
            [("zero", [0, 0]), ("negatives", [-1, -1]), ("off by one", [10, 11])],
            edges=[("large equal", [10 ** 9, 10 ** 9])],
            difficulty="GUIDED", family="oop_eq_hash", after="oopl-repr-roundtrip-easy",
            cmp="bool",
            starter="""
            class Badge:
                def __init__(self, number):
                    self.number = number

                def __eq__(self, other):
                    if not isinstance(other, Badge):
                        return NotImplemented
                    # Two badges match when their numbers do.
                    return __BLANK__


            def badges_equal(a, b):
                return Badge(a) == Badge(b)
            """,
            nudge="Returning `NotImplemented` for a foreign type is the polite "
                  "form: it lets the other object try its own __eq__ before "
                  "Python falls back to identity.",
            pseudocode="return self.number == other.number",
            fragment=_same_move("return self.user_id == other.user_id"),
            failures=["`return self is other`, which is the default you were "
                      "replacing",
                      "`return self.number is other.number`, which only happens to "
                      "work for small integers"],
            tags=["dunder", "eq"],
        ),

        _oop(
            "oopl-eq-default-tutorial", "Identity Is The Default",
            """
            Before you write `__eq__`, `==` on your class means "the same object in
            memory". Two freshly built objects with identical contents are not
            equal, and that surprises people in review far more often than it
            should.

            `Plain` has no `__eq__`. Return
            `[Plain(v) == Plain(v), obj == obj, Plain(v) != Plain(v)]`.
            """,
            "default_equality", "value", _ref_default_equality,
            """
            class Plain:
                def __init__(self, value):
                    self.value = value


            def default_equality(value):
                first = Plain(value)
                second = Plain(value)
                # Same contents, different objects. Python's default says no.
                return [first == second, first == first, first != second]
            """,
            [("integer", [5]), ("string", ["abc"])],
            [("zero", [0]), ("empty string", [""]), ("none", [None])],
            edges=[("negative", [-1])],
            difficulty="TUTORIAL", family="oop_eq_hash", after="oopl-eq-guided",
            starter="""
            class Plain:
                def __init__(self, value):
                    self.value = value


            def default_equality(value):
                first = Plain(value)
                second = Plain(value)
                # compare two separate objects, then one object with itself
                pass
            """,
            nudge="`!=` is derived from `__eq__` automatically in Python 3. You do "
                  "not write `__ne__`.",
            pseudocode="first = Plain(value); second = Plain(value)\n"
                       "return [first == second, first == first, first != second]",
            failures=["Assuming dataclass-style value equality comes for free"],
            tags=["dunder", "eq", "identity"],
        ),

        _oop(
            "oopl-eq-hash-easy", "Equal Things Must Hash Alike",
            """
            A set and a dict find things by hash first and confirm with `==`. So an
            object that defines `__eq__` must define a `__hash__` that agrees:
            equal objects, equal hashes. Hash a tuple of the same fields you
            compare and the rule is satisfied by construction.

            Write `Point` with both, then return the distinct points, sorted.
            """,
            "unique_points", "pairs", _ref_unique_points,
            """
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def __eq__(self, other):
                    if not isinstance(other, Point):
                        return NotImplemented
                    return (self.x, self.y) == (other.x, other.y)

                def __hash__(self):
                    # Same fields as __eq__, in the same order. Anything else
                    # eventually puts two equal points in one set.
                    return hash((self.x, self.y))


            def unique_points(pairs):
                distinct = {Point(x, y) for x, y in pairs}
                return sorted([[point.x, point.y] for point in distinct])
            """,
            [("one duplicate", [[[1, 2], [1, 2], [3, 4]]]),
             ("all distinct", [[[0, 0], [1, 1]]])],
            [("all the same", [[[5, 5], [5, 5], [5, 5]]]),
             ("negatives", [[[-1, 0], [-1, 0], [0, -1]]]),
             ("swapped is different", [[[1, 2], [2, 1]]])],
            edges=[("no points", [[]]), ("single", [[[9, 9]]])],
            difficulty="EASY", family="oop_eq_hash", after="oopl-eq-default-tutorial",
            pattern="HASH_MAP", secondary=["SET"],
            starter="""
            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def __eq__(self, other):
                    pass

                def __hash__(self):
                    pass


            def unique_points(pairs):
                pass
            """,
            nudge="`hash((self.x, self.y))` is not a trick. Tuples of hashable "
                  "things are hashable, and that is the whole implementation.",
            pseudocode="__eq__: compare the field tuples\n__hash__: hash the field "
                       "tuple\nunique: build a set, sort what comes out",
            failures=["`hash(self.x)` alone — (1, 2) and (1, 99) then collide "
                      "constantly and the set gets slow, not wrong",
                      "Hashing a mutable field, which makes the object move in the "
                      "set the moment anyone edits it"],
            time="O(n)", space="O(n)", tags=["dunder", "eq", "hash"],
        ),

        _oop(
            "oopl-eq-without-hash-medium", "The Set That Refuses You",
            """
            Defining `__eq__` and stopping there does something people rarely
            expect: Python sets `__hash__` to None for you, and your objects stop
            working in sets and dict keys entirely.

            Three classes are given: `Plain` (neither), `EqOnly` (`__eq__` only)
            and `EqAndHash` (both). `hashability_report(kind)` builds
            `{cls(1), cls(1)}` and returns `["ok", size]`, or `["error", "TypeError"]`
            if that is not allowed.
            """,
            "hashability_report", "kind", _ref_hashability,
            """
            class Plain:
                def __init__(self, value):
                    self.value = value


            class EqOnly:
                def __init__(self, value):
                    self.value = value

                def __eq__(self, other):
                    if not isinstance(other, EqOnly):
                        return NotImplemented
                    return self.value == other.value


            class EqAndHash(EqOnly):
                # Defining __eq__ anywhere sets __hash__ = None on that class.
                # Restoring it is a deliberate act.
                def __hash__(self):
                    return hash(self.value)


            def hashability_report(kind):
                cls = {"plain": Plain, "eq_only": EqOnly,
                       "eq_and_hash": EqAndHash}[kind]
                try:
                    return ["ok", len({cls(1), cls(1)})]
                except TypeError:
                    return ["error", "TypeError"]
            """,
            [("eq only", ["eq_only"]), ("both", ["eq_and_hash"])],
            [("neither", ["plain"]), ("eq only again", ["eq_only"]),
             ("both again", ["eq_and_hash"])],
            edges=[("default identity semantics", ["plain"])],
            difficulty="MEDIUM", family="oop_eq_hash", after="oopl-eq-hash-easy",
            pattern="HASH_MAP", secondary=["SET"],
            starter="""
            class Plain:
                def __init__(self, value):
                    self.value = value


            class EqOnly:
                def __init__(self, value):
                    self.value = value

                def __eq__(self, other):
                    pass


            class EqAndHash(EqOnly):
                def __hash__(self):
                    pass


            def hashability_report(kind):
                pass
            """,
            nudge="`Plain` has no __eq__, so it keeps the identity hash and two "
                  "separate objects are two separate set members. That is the "
                  "answer for the first case, and it is 2, not 1.",
            pseudocode="pick the class\ntry: return ['ok', len({cls(1), cls(1)})]\n"
                       "except TypeError: return ['error', 'TypeError']",
            failures=["Expecting `eq_only` to give 1 — it gives an unhashable-type "
                      "TypeError before equality is ever consulted",
                      "Expecting `plain` to give 1 — nothing there says those two "
                      "objects are the same"],
            tags=["dunder", "eq", "hash"],
        ),

        # ==================================================================
        # 7. __len__, __getitem__, __contains__
        # ==================================================================
        _oop(
            "oopl-len-guided", "How Big Are You",
            """
            `len(obj)` calls `obj.__len__()`. That is the entire mechanism. A class
            that wraps a collection usually just forwards the question.

            Fill in `__len__` so `len(bag)` reports how many items it holds.
            """,
            "bag_size", "items", _ref_bag_size,
            """
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __len__(self):
                    return len(self.items)


            def bag_size(items):
                return len(Bag(items))
            """,
            [("three", [[1, 2, 3]]), ("one", [["x"]])],
            [("duplicates still count", [[1, 1, 1]]), ("strings", [["a", "b"]]),
             ("nested", [[[1], [2]]])],
            edges=[("empty", [[]])],
            difficulty="GUIDED", family="oop_container",
            after="oopl-eq-without-hash-medium",
            starter="""
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __len__(self):
                    # Forward the question to the list you are wrapping.
                    return __BLANK__


            def bag_size(items):
                return len(Bag(items))
            """,
            nudge="`__len__` must return a non-negative integer. Returning a float "
                  "or a string raises TypeError at the call site, not in your method.",
            pseudocode="return len(self.items)",
            fragment=_same_move("def __len__(self):\n    return len(self.rows)"),
            failures=["`return self.items`, which is a list, not a length",
                      "Defining `length()` instead, which `len()` will never find"],
            pattern="ARRAY", tags=["dunder", "len"],
        ),

        _oop(
            "oopl-getitem-tutorial", "Square Brackets Are A Method Call",
            """
            `bag[3]` is `bag.__getitem__(3)`. Forwarding it to a list gets you
            negative indices and slices for free, because the list already
            implements them.

            Write `__getitem__` on `Bag`, then return `bag[index]`.
            """,
            "bag_at", "items, index", _ref_bag_at,
            """
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __getitem__(self, index):
                    return self.items[index]


            def bag_at(items, index):
                return Bag(items)[index]
            """,
            [("first", [[10, 20, 30], 0]), ("last by negative index", [[10, 20, 30], -1])],
            [("middle", [["a", "b", "c"], 1]), ("second from the end", [[1, 2, 3], -2]),
             ("single item", [[7], 0])],
            edges=[("negative into a two-item bag", [[1, 2], -2])],
            difficulty="TUTORIAL", family="oop_container", after="oopl-len-guided",
            starter="""
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __getitem__(self, index):
                    # hand the index straight to the wrapped list
                    pass


            def bag_at(items, index):
                return Bag(items)[index]
            """,
            nudge="You are not writing index arithmetic. You are delegating.",
            pseudocode="return self.items[index]",
            failures=["Rejecting negative indices by hand and losing behaviour the "
                      "list already had"],
            pattern="ARRAY", tags=["dunder", "getitem"],
        ),

        _oop(
            "oopl-container-easy", "The Whole Container Protocol",
            """
            Three dunders make an object feel like a built-in collection:
            `__len__` for `len()`, `__getitem__` for `[]`, and `__contains__` for
            `in`. Define `__getitem__` alone and `in` and `for` already work by
            walking indices until IndexError — `__contains__` just makes it direct.

            Write `Roster` with all three. `roster_report` returns
            `[len(roster), probe in roster, list(roster), last item or None]`.
            """,
            "roster_report", "names, probe", _ref_roster_report,
            """
            class Roster:
                def __init__(self, names):
                    self.names = list(names)

                def __len__(self):
                    return len(self.names)

                def __getitem__(self, index):
                    return self.names[index]

                def __contains__(self, name):
                    return name in self.names


            def roster_report(names, probe):
                roster = Roster(names)
                last = roster[-1] if len(roster) else None
                return [len(roster), probe in roster, list(roster), last]
            """,
            [("present", [["ada", "grace", "alan"], "grace"]),
             ("absent", [["ada", "grace"], "linus"])],
            [("first item", [["a", "b"], "a"]), ("duplicate names", [["a", "a"], "a"]),
             ("single", [["solo"], "solo"])],
            edges=[("empty roster", [[], "anyone"])],
            difficulty="EASY", family="oop_container", after="oopl-getitem-tutorial",
            pattern="ARRAY",
            starter="""
            class Roster:
                def __init__(self, names):
                    self.names = list(names)

                def __len__(self):
                    pass

                def __getitem__(self, index):
                    pass

                def __contains__(self, name):
                    pass


            def roster_report(names, probe):
                pass
            """,
            nudge="The empty case is the one that bites: `roster[-1]` on an empty "
                  "roster raises. Check the length first.",
            pseudocode="len -> len(self.names)\ngetitem -> self.names[index]\n"
                       "contains -> name in self.names\n"
                       "report: [len, probe in roster, list(roster), last or None]",
            failures=["Returning a truthy non-boolean from __contains__ — Python "
                      "coerces it, which hides the sloppiness until someone "
                      "compares the result to True",
                      "Indexing [-1] without checking for the empty case"],
            time="O(n)", tags=["dunder", "len", "getitem", "contains"],
        ),

        # ==================================================================
        # 8. __iter__
        # ==================================================================
        _oop(
            "oopl-iter-guided", "Something A For Loop Will Accept",
            """
            `for x in obj` calls `obj.__iter__()` and expects an iterator back. The
            simplest honest implementation hands back the iterator of whatever you
            are wrapping.

            Fill in `__iter__`.
            """,
            "iterate_bag", "items", _ref_iterate_bag,
            """
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __iter__(self):
                    return iter(self.items)


            def iterate_bag(items):
                return list(Bag(items))
            """,
            [("three", [[1, 2, 3]]), ("strings", [["a", "b"]])],
            [("duplicates", [[1, 1]]), ("single", [[9]]), ("mixed", [[1, "a", None]])],
            edges=[("empty", [[]])],
            difficulty="GUIDED", family="oop_iter", after="oopl-container-easy",
            starter="""
            class Bag:
                def __init__(self, items):
                    self.items = list(items)

                def __iter__(self):
                    # Return an ITERATOR, not the list itself.
                    return __BLANK__


            def iterate_bag(items):
                return list(Bag(items))
            """,
            nudge="`return self.items` is the near miss: a list is iterable, but it "
                  "is not an iterator, and `__iter__` must return an iterator.",
            pseudocode="return iter(self.items)",
            fragment=_same_move("def __iter__(self):\n    return iter(self.rows)"),
            failures=["Returning the list itself and getting 'iter() returned "
                      "non-iterator'"],
            pattern="ARRAY", tags=["dunder", "iter"],
        ),

        _oop(
            "oopl-iter-generator-tutorial", "Yield Makes It An Iterator",
            """
            A `__iter__` that contains `yield` is a generator function, so calling
            it returns a generator — which is already an iterator. This is the
            shortest way to iterate over something computed rather than stored.

            Write `Doubler.__iter__` so iterating yields each number doubled.
            """,
            "doubled", "nums", _ref_doubled,
            """
            class Doubler:
                def __init__(self, nums):
                    self.nums = list(nums)

                def __iter__(self):
                    for number in self.nums:
                        yield number * 2


            def doubled(nums):
                return list(Doubler(nums))
            """,
            [("small", [[1, 2, 3]]), ("negatives", [[-1, -5]])],
            [("zeros", [[0, 0]]), ("single", [[21]]), ("large", [[10 ** 6]])],
            edges=[("empty", [[]])],
            difficulty="TUTORIAL", family="oop_iter", after="oopl-iter-guided",
            starter="""
            class Doubler:
                def __init__(self, nums):
                    self.nums = list(nums)

                def __iter__(self):
                    # one `yield` per value you want the loop to see
                    pass


            def doubled(nums):
                return list(Doubler(nums))
            """,
            nudge="Nothing runs until something iterates. A generator body is lazy "
                  "by construction.",
            pseudocode="for number in self.nums: yield number * 2",
            failures=["Building a list and returning it — that works, and it also "
                      "loses the laziness that was the point"],
            pattern="ARRAY", time="O(n)", tags=["dunder", "iter", "generator"],
        ),

        _oop(
            "oopl-iter-exhaust-easy", "The Iterator That Only Works Once",
            """
            An ITERABLE can be walked many times. An ITERATOR is a one-shot cursor:
            once it raises `StopIteration` it stays exhausted. A class whose
            `__iter__` returns `self` is its own cursor, so the second loop over it
            sees nothing at all.

            Write `Countdown` with `__iter__` and `__next__`, counting from `start`
            down to 1. Return the result of listing it twice.
            """,
            "countdown_twice", "start", _ref_countdown_twice,
            """
            class Countdown:
                def __init__(self, start):
                    self.current = start

                def __iter__(self):
                    # Returning self is what makes this a one-shot iterator.
                    return self

                def __next__(self):
                    if self.current <= 0:
                        raise StopIteration
                    self.current -= 1
                    return self.current + 1


            def countdown_twice(start):
                counter = Countdown(start)
                return [list(counter), list(counter)]
            """,
            [("from three", [3]), ("from one", [1])],
            [("from five", [5]), ("from two", [2]), ("from ten", [10])],
            edges=[("from zero", [0]), ("negative start", [-3])],
            difficulty="EASY", family="oop_iter",
            after="oopl-iter-generator-tutorial",
            starter="""
            class Countdown:
                def __init__(self, start):
                    pass

                def __iter__(self):
                    pass

                def __next__(self):
                    # raise StopIteration when there is nothing left
                    pass


            def countdown_twice(start):
                counter = Countdown(start)
                return [list(counter), list(counter)]
            """,
            nudge="`StopIteration` is raised, not returned. Returning None instead "
                  "gives you an infinite loop of Nones.",
            pseudocode="__iter__: return self\n__next__: if current <= 0: raise "
                       "StopIteration; decrement and return the old value",
            failures=["Expecting the second list to repeat the first",
                      "Resetting the counter inside __iter__, which quietly makes "
                      "it re-iterable and hides the lesson"],
            time="O(n)", tags=["dunder", "iter", "next"],
        ),

        # ==================================================================
        # 9. __lt__ and ordering
        # ==================================================================
        _oop(
            "oopl-lt-guided", "Teaching sorted() What Smaller Means",
            """
            `sorted()`, `min()` and `max()` all ask one question: is a < b. That
            question is `__lt__`. Define it and your objects sort themselves.

            A run is faster, and therefore smaller, when its seconds are fewer.
            Fill in the comparison.
            """,
            "fastest_first", "rows", _ref_fastest_first,
            """
            class Run:
                def __init__(self, name, seconds):
                    self.name = name
                    self.seconds = seconds

                def __lt__(self, other):
                    return self.seconds < other.seconds


            def fastest_first(rows):
                runs = [Run(name, seconds) for name, seconds in rows]
                return [run.name for run in sorted(runs)]
            """,
            [("three runs", [[["ada", 12], ["bel", 9], ["cy", 30]]]),
             ("already ordered", [[["a", 1], ["b", 2]]])],
            [("reversed", [[["a", 3], ["b", 2], ["c", 1]]]),
             ("single", [[["solo", 5]]]),
             ("zero seconds", [[["a", 0], ["b", 1]]])],
            edges=[("no runs", [[]])],
            difficulty="GUIDED", family="oop_ordering", after="oopl-iter-exhaust-easy",
            pattern="SORTING",
            starter="""
            class Run:
                def __init__(self, name, seconds):
                    self.name = name
                    self.seconds = seconds

                def __lt__(self, other):
                    # Fewer seconds means smaller.
                    return __BLANK__


            def fastest_first(rows):
                runs = [Run(name, seconds) for name, seconds in rows]
                return [run.name for run in sorted(runs)]
            """,
            nudge="You only have to define `<`. Python's sort never asks for `>`.",
            pseudocode="return self.seconds < other.seconds",
            fragment=_same_move("return self.priority < other.priority"),
            failures=["Comparing the names by mistake, which sorts alphabetically",
                      "Writing `>` and getting the slowest first"],
            time="O(n log n)", tags=["dunder", "lt", "sorting"],
        ),

        _oop(
            "oopl-lt-tuple-tutorial", "Breaking The Tie",
            """
            Compare a tuple of fields and you get tie-breaking for free: tuples
            compare left to right and only look at the second element when the
            first ties.

            Order runs by seconds, then by name for equal times.
            """,
            "fastest_with_tiebreak", "rows", _ref_fastest_with_tiebreak,
            """
            class Run:
                def __init__(self, name, seconds):
                    self.name = name
                    self.seconds = seconds

                def __lt__(self, other):
                    # One comparison, two keys, in priority order.
                    return (self.seconds, self.name) < (other.seconds, other.name)


            def fastest_with_tiebreak(rows):
                runs = [Run(name, seconds) for name, seconds in rows]
                return [run.name for run in sorted(runs)]
            """,
            [("one tie", [[["zed", 9], ["ada", 9], ["bel", 4]]]),
             ("no ties", [[["a", 2], ["b", 1]]])],
            [("all tied", [[["c", 1], ["a", 1], ["b", 1]]]),
             ("two ties", [[["b", 5], ["a", 5], ["d", 2], ["c", 2]]]),
             ("single", [[["only", 3]]])],
            edges=[("empty", [[]])],
            difficulty="TUTORIAL", family="oop_ordering", after="oopl-lt-guided",
            pattern="SORTING",
            starter="""
            class Run:
                def __init__(self, name, seconds):
                    self.name = name
                    self.seconds = seconds

                def __lt__(self, other):
                    # compare (seconds, name) against (seconds, name)
                    pass


            def fastest_with_tiebreak(rows):
                runs = [Run(name, seconds) for name, seconds in rows]
                return [run.name for run in sorted(runs)]
            """,
            nudge="Python's sort is stable, so without a tie-break the original "
                  "order survives — which is a different answer, not a wrong one.",
            pseudocode="return (self.seconds, self.name) < (other.seconds, other.name)",
            failures=["Chaining `and`/`or` by hand and getting the equal case wrong"],
            time="O(n log n)", tags=["dunder", "lt", "sorting"],
        ),

        _oop(
            "oopl-ordering-easy", "min, max And sorted, All From One Method",
            """
            One `__lt__` is enough for the whole family: `min` finds the smallest
            by asking `<` repeatedly, `max` does the same in reverse, and `sorted`
            uses it throughout.

            Write `Score` with `__lt__` on `points`, then return
            `[lowest name, highest name, all names in order]`.
            """,
            "podium", "rows", _ref_podium,
            """
            class Score:
                def __init__(self, name, points):
                    self.name = name
                    self.points = points

                def __lt__(self, other):
                    return self.points < other.points


            def podium(rows):
                scores = [Score(name, points) for name, points in rows]
                ordered = sorted(scores)
                return [min(scores).name, max(scores).name,
                        [score.name for score in ordered]]
            """,
            [("three", [[["ada", 30], ["bel", 10], ["cy", 20]]]),
             ("two", [[["a", 1], ["b", 2]]])],
            [("negatives", [[["a", -5], ["b", 0]]]),
             ("descending input", [[["a", 9], ["b", 5], ["c", 1]]]),
             ("single", [[["solo", 7]]])],
            edges=[("tie keeps input order", [[["a", 5], ["b", 5]]])],
            difficulty="EASY", family="oop_ordering", after="oopl-lt-tuple-tutorial",
            pattern="SORTING",
            starter="""
            class Score:
                def __init__(self, name, points):
                    self.name = name
                    self.points = points

                def __lt__(self, other):
                    pass


            def podium(rows):
                pass
            """,
            nudge="On a tie, `min` keeps the first it saw and `max` keeps the first "
                  "it saw. Both answers come from the same rule.",
            pseudocode="__lt__ on points\nordered = sorted(scores)\n"
                       "return [min(scores).name, max(scores).name, names of ordered]",
            failures=["Writing separate __gt__ and __le__ methods that disagree with "
                      "__lt__ — use functools.total_ordering if you genuinely need "
                      "all six"],
            time="O(n log n)", tags=["dunder", "lt", "sorting"],
        ),

        # ==================================================================
        # 10. @property and its setter
        # ==================================================================
        _oop(
            "oopl-property-guided", "A Method That Looks Like An Attribute",
            """
            `@property` turns a method into a read-only attribute. Callers write
            `rect.area`, with no parentheses, and your code runs. It is how you
            change a stored value into a computed one without touching a single
            caller.

            Fill in the computation.
            """,
            "rect_area", "width, height", _ref_rect_area,
            """
            class Rect:
                def __init__(self, width, height):
                    self.width = width
                    self.height = height

                @property
                def area(self):
                    return self.width * self.height


            def rect_area(width, height):
                return Rect(width, height).area
            """,
            [("square", [3, 3]), ("rectangle", [4, 5])],
            [("one wide", [1, 10]), ("zero height", [7, 0]), ("large", [1000, 1000])],
            edges=[("both zero", [0, 0])],
            difficulty="GUIDED", family="oop_property", after="oopl-ordering-easy",
            starter="""
            class Rect:
                def __init__(self, width, height):
                    self.width = width
                    self.height = height

                @property
                def area(self):
                    # Computed on every read. No parentheses at the call site.
                    return __BLANK__


            def rect_area(width, height):
                return Rect(width, height).area
            """,
            nudge="Note the call site: `.area`, not `.area()`. Adding the "
                  "parentheses is how you find out a property is a property.",
            pseudocode="return self.width * self.height",
            fragment=_same_move("@property\ndef full_name(self):\n    "
                                "return self.first + ' ' + self.last"),
            failures=["Storing `self.area` in __init__ instead, which goes stale the "
                      "moment width changes"],
            tags=["property"],
        ),

        _oop(
            "oopl-property-setter-tutorial", "The Setter Writes Backwards",
            """
            A property can have a setter. The classic use is a second view onto one
            stored value: `Temperature` stores celsius, and the `fahrenheit`
            property converts on read and converts back on write.

            Return `[the fahrenheit reading, the celsius after setting fahrenheit
            to target_f]`.
            """,
            "temp_convert", "celsius, target_f", _ref_temp_convert,
            """
            class Temperature:
                def __init__(self, celsius):
                    self.celsius = celsius

                @property
                def fahrenheit(self):
                    return self.celsius * 9 / 5 + 32

                @fahrenheit.setter
                def fahrenheit(self, value):
                    # There is only one stored number. This writes to it.
                    self.celsius = (value - 32) * 5 / 9


            def temp_convert(celsius, target_f):
                reading = Temperature(celsius)
                first = reading.fahrenheit
                reading.fahrenheit = target_f
                return [first, reading.celsius]
            """,
            [("freezing to boiling", [0, 212]), ("body heat", [37, 32])],
            [("negative", [-40, -40]), ("room", [21, 68]), ("zero target", [100, 0])],
            edges=[("no change", [0, 32])],
            difficulty="TUTORIAL", family="oop_property", cmp="float_list",
            after="oopl-property-guided",
            starter="""
            class Temperature:
                def __init__(self, celsius):
                    self.celsius = celsius

                @property
                def fahrenheit(self):
                    # celsius -> fahrenheit
                    pass

                @fahrenheit.setter
                def fahrenheit(self, value):
                    # fahrenheit -> celsius, stored back on self.celsius
                    pass


            def temp_convert(celsius, target_f):
                pass
            """,
            nudge="The setter is named `fahrenheit` too, and decorated with "
                  "`@fahrenheit.setter`. Renaming it breaks the pairing.",
            pseudocode="getter: c * 9 / 5 + 32\nsetter: self.celsius = (v - 32) * 5 / 9",
            failures=["Using `//` and truncating every conversion",
                      "Storing fahrenheit as well, giving two numbers that drift apart"],
            tags=["property", "setter"],
        ),

        _oop(
            "oopl-property-validate-easy", "The Setter That Says No",
            """
            The real reason to reach for a property is validation: a plain
            attribute can be set to anything, a setter can refuse.

            Write `Account` so the balance is stored privately and the setter
            raises `ValueError("balance cannot be negative")` for a negative value.
            Note that `__init__` assigning `self.balance` goes through the setter
            too, so the check applies at construction for free.
            """,
            "open_account", "amount", _ref_open_account,
            """
            class Account:
                def __init__(self, balance):
                    # Not self._balance: assigning the property runs the setter,
                    # which is how construction gets validated for free.
                    self.balance = balance

                @property
                def balance(self):
                    return self._balance

                @balance.setter
                def balance(self, value):
                    if value < 0:
                        raise ValueError("balance cannot be negative")
                    self._balance = value


            def open_account(amount):
                try:
                    return ["ok", Account(amount).balance]
                except ValueError as exc:
                    return ["error", str(exc)]
            """,
            [("valid", [100]), ("refused", [-1])],
            [("zero is fine", [0]), ("large", [10 ** 9]), ("very negative", [-500])],
            edges=[("minus zero", [0])],
            difficulty="EASY", family="oop_property",
            after="oopl-property-setter-tutorial",
            starter="""
            class Account:
                def __init__(self, balance):
                    pass

                @property
                def balance(self):
                    pass

                @balance.setter
                def balance(self, value):
                    pass


            def open_account(amount):
                pass
            """,
            nudge="The getter returns `self._balance` and the setter writes "
                  "`self._balance`. If either one touches `self.balance` you get "
                  "infinite recursion.",
            pseudocode="__init__: self.balance = balance\ngetter: return self._balance\n"
                       "setter: refuse negatives, else self._balance = value",
            failures=["`self.balance = value` inside the setter — RecursionError",
                      "Validating in __init__ only, so a later assignment slips past"],
            tags=["property", "setter", "validation"],
        ),

        _oop(
            "oopl-property-readonly-medium", "Computed Means Read-Only",
            """
            A property with a getter and no setter cannot be assigned. Python
            raises `AttributeError`, and that is a feature: it stops a caller from
            replacing a derived value with a stale constant.

            `freeze_report` tries to assign `rect.area` and reports `["assigned", ...]`
            or `["refused", ...]` along with the area as it actually stands
            afterwards.
            """,
            "freeze_report", "width, height, new_area", _ref_freeze_report,
            """
            class Rect:
                def __init__(self, width, height):
                    self.width = width
                    self.height = height

                @property
                def area(self):
                    return self.width * self.height


            def freeze_report(width, height, new_area):
                rect = Rect(width, height)
                try:
                    rect.area = new_area
                    return ["assigned", rect.area]
                except AttributeError:
                    # No setter was defined, so the attribute refuses the write.
                    return ["refused", rect.area]
            """,
            [("refuses a lie", [3, 4, 99]), ("refuses the truth too", [2, 5, 10])],
            [("zero area", [0, 9, 1]), ("square", [6, 6, 0]), ("large", [100, 100, 1])],
            edges=[("assign the same value", [2, 2, 4])],
            difficulty="MEDIUM", family="oop_property",
            after="oopl-property-validate-easy",
            starter="""
            class Rect:
                def __init__(self, width, height):
                    self.width = width
                    self.height = height

                @property
                def area(self):
                    pass


            def freeze_report(width, height, new_area):
                pass
            """,
            nudge="Assigning the same value it already had is still refused. The "
                  "property does not compare, it simply has nowhere to put it.",
            pseudocode="try: rect.area = new_area; return ['assigned', rect.area]\n"
                       "except AttributeError: return ['refused', rect.area]",
            failures=["Catching `Exception` here, which would also hide a typo in "
                      "the attribute name",
                      "Expecting the assignment to silently create an instance "
                      "attribute — a data descriptor on the class wins over the "
                      "instance dict"],
            tags=["property", "attribute-error"],
        ),

        # ==================================================================
        # 11. @staticmethod vs @classmethod
        # ==================================================================
        _oop(
            "oopl-staticmethod-guided", "A Function That Lives In A Class",
            """
            `@staticmethod` marks a method that receives nothing automatically —
            no `self`, no `cls`. It is a plain function that lives inside the class
            because that is where it belongs conceptually.

            Fill in the body of `shout`.
            """,
            "shout", "text", _ref_shout,
            """
            class TextTools:
                @staticmethod
                def shout(text):
                    # No `self` parameter. There is no object here to have one.
                    return text.upper()


            def shout(text):
                return TextTools.shout(text)
            """,
            [("word", ["hello"]), ("mixed", ["MiXeD"])],
            [("already loud", ["LOUD"]), ("with spaces", ["two words"]),
             ("digits survive", ["a1b2"])],
            edges=[("empty", [""])],
            difficulty="GUIDED", family="oop_methods",
            after="oopl-property-readonly-medium", pattern="STRING",
            starter="""
            class TextTools:
                @staticmethod
                def shout(text):
                    # No `self` here: a static method gets exactly what it is passed.
                    return __BLANK__


            def shout(text):
                return TextTools.shout(text)
            """,
            nudge="Because there is no `self`, you can call it on the class itself: "
                  "`TextTools.shout(...)`, no instance required.",
            pseudocode="return text.upper()",
            fragment=_same_move("@staticmethod\ndef is_blank(text):\n    "
                                "return text.strip() == ''"),
            failures=["Adding a `self` parameter and then calling it on the class, "
                      "which hands `text` to `self`"],
            tags=["staticmethod"],
        ),

        _oop(
            "oopl-classmethod-tutorial", "The Alternative Constructor",
            """
            `@classmethod` receives the class as its first argument, spelled `cls`.
            Its most common job by far is the alternative constructor: a named way
            to build an instance from some other representation.

            Write `Date.from_iso("2026-09-11")`, which splits on "-" and builds a
            Date from the three integers.
            """,
            "parse_date", "text", _ref_parse_date,
            """
            class Date:
                def __init__(self, year, month, day):
                    self.year = year
                    self.month = month
                    self.day = day

                @classmethod
                def from_iso(cls, text):
                    year, month, day = text.split("-")
                    # cls(...), not Date(...). The difference matters to subclasses.
                    return cls(int(year), int(month), int(day))


            def parse_date(text):
                date = Date.from_iso(text)
                return [date.year, date.month, date.day]
            """,
            [("today", ["2026-09-11"]), ("new year", ["2000-01-01"])],
            [("single digits", ["1999-1-2"]), ("end of year", ["2024-12-31"]),
             ("year one", ["0001-01-01"])],
            edges=[("leap day", ["2024-02-29"])],
            difficulty="TUTORIAL", family="oop_methods",
            after="oopl-staticmethod-guided",
            starter="""
            class Date:
                def __init__(self, year, month, day):
                    self.year = year
                    self.month = month
                    self.day = day

                @classmethod
                def from_iso(cls, text):
                    # split, convert to int, and build with cls
                    pass


            def parse_date(text):
                date = Date.from_iso(text)
                return [date.year, date.month, date.day]
            """,
            nudge="`text.split(\"-\")` gives you three strings. `int()` each of them "
                  "before handing them over.",
            pseudocode="year, month, day = text.split('-')\n"
                       "return cls(int(year), int(month), int(day))",
            failures=["Forgetting `int()` and storing strings that look right in a "
                      "print and compare wrong everywhere else"],
            pattern="STRING", tags=["classmethod", "constructor"],
        ),

        _oop(
            "oopl-static-vs-class-easy", "cls Knows Who Called It",
            """
            The difference in one sentence: a static method knows nothing about the
            class, a class method receives it.

            Write `Tool.stat` (static, returns `"static:" + value`) and `Tool.named`
            (a classmethod returning `cls.__name__ + ":" + value`). `SubTool`
            inherits both. Return
            `[Tool.stat(v), Tool.named(v), SubTool.named(v)]`.
            """,
            "method_kinds", "value", _ref_method_kinds,
            """
            class Tool:
                @staticmethod
                def stat(value):
                    return "static:" + value

                @classmethod
                def named(cls, value):
                    # cls is whichever class the call went through.
                    return cls.__name__ + ":" + value


            class SubTool(Tool):
                pass


            def method_kinds(value):
                return [Tool.stat(value), Tool.named(value), SubTool.named(value)]
            """,
            [("word", ["run"]), ("letter", ["x"])],
            [("digits", ["42"]), ("spaces", ["a b"]), ("underscore", ["_"])],
            edges=[("empty", [""])],
            difficulty="EASY", family="oop_methods", after="oopl-classmethod-tutorial",
            pattern="STRING",
            starter="""
            class Tool:
                @staticmethod
                def stat(value):
                    pass

                @classmethod
                def named(cls, value):
                    pass


            class SubTool(Tool):
                pass


            def method_kinds(value):
                pass
            """,
            nudge="`SubTool.named` was never redefined, and it still reports "
                  "SubTool. That is the whole point of receiving `cls`.",
            pseudocode="stat -> 'static:' + value\nnamed -> cls.__name__ + ':' + value",
            failures=["Hardcoding `Tool.__name__` in the classmethod, which makes "
                      "the subclass lie"],
            tags=["staticmethod", "classmethod"],
        ),

        _oop(
            "oopl-classmethod-inherit-medium", "Why The Factory Uses cls",
            """
            This is the question behind the interview question. A factory written
            as `@classmethod ... return cls(size)` builds the subclass when called
            on the subclass. The same factory written as a staticmethod naming the
            base class hardcodes the wrong type, and nobody notices until someone
            subclasses it.

            Return `[type of Square.make(size), type of Square.make_badly(size),
            the size that survived]`, using class NAMES.
            """,
            "constructor_kinds", "size", _ref_constructor_kinds,
            """
            class Shape:
                def __init__(self, size):
                    self.size = size

                @classmethod
                def make(cls, size):
                    return cls(size)

                @staticmethod
                def make_badly(size):
                    # Hardcoded. Square.make_badly(3) still gives you a Shape.
                    return Shape(size)


            class Square(Shape):
                pass


            def constructor_kinds(size):
                good = Square.make(size)
                bad = Square.make_badly(size)
                return [type(good).__name__, type(bad).__name__, good.size]
            """,
            [("small", [2]), ("larger", [10])],
            [("zero", [0]), ("negative", [-4]), ("big", [10 ** 6])],
            edges=[("one", [1])],
            difficulty="MEDIUM", family="oop_methods", after="oopl-static-vs-class-easy",
            starter="""
            class Shape:
                def __init__(self, size):
                    self.size = size

                @classmethod
                def make(cls, size):
                    pass

                @staticmethod
                def make_badly(size):
                    pass


            class Square(Shape):
                pass


            def constructor_kinds(size):
                pass
            """,
            nudge="`type(obj).__name__` is the honest way to ask what something is. "
                  "`obj.__class__.__name__` says the same thing.",
            pseudocode="make: return cls(size)\nmake_badly: return Shape(size)\n"
                       "report both type names and the size",
            failures=["Expecting both to report Square — the staticmethod has no "
                      "idea a subclass exists",
                      "Using `isinstance` for this report, which is True for both "
                      "and therefore answers a different question"],
            tags=["classmethod", "staticmethod", "inheritance"],
        ),

        # ==================================================================
        # 12. isinstance, type, ABCs, duck typing
        # ==================================================================
        _oop(
            "oopl-type-guided", "Asking What Something Is",
            """
            `type(value)` gives the class object. `.__name__` gives its name as a
            string. Together they are the quickest honest answer to "what did I
            just get handed".

            Fill in the expression that names each value's type.
            """,
            "type_names", "values", _ref_type_names,
            """
            def type_names(values):
                return [type(value).__name__ for value in values]
            """,
            [("mixed", [[1, "a", 2.5]]), ("containers", [[[], {}]])],
            [("none", [[None]]), ("booleans", [[True, False]]),
             ("all strings", [["a", "b"]])],
            edges=[("empty list of values", [[]])],
            difficulty="GUIDED", family="oop_typing",
            after="oopl-classmethod-inherit-medium",
            starter="""
            def type_names(values):
                # type(value) is the class. .__name__ is what it is called.
                return [__BLANK__ for value in values]
            """,
            nudge="`type(value)` prints as `<class 'int'>`. The bare name lives on "
                  "`__name__`.",
            pseudocode="for each value: type(value).__name__",
            fragment=_same_move("kind = type(payload).__name__"),
            failures=["`str(type(value))`, which gives \"<class 'int'>\" and not "
                      "\"int\""],
            time="O(n)", tags=["type", "introspection"],
        ),

        _oop(
            "oopl-isinstance-tutorial", "isinstance Counts The Family",
            """
            `isinstance(obj, Cls)` is True for subclasses. `type(obj) is Cls` is
            True only for that exact class. Almost always you want the first one,
            because a subclass is supposed to be usable wherever its parent is.

            Return `[isinstance(obj, Animal), type(obj) is Animal]` for the chosen
            object.
            """,
            "check_kinds", "which", _ref_check_kinds,
            """
            class Animal:
                pass


            class Dog(Animal):
                pass


            def check_kinds(which):
                obj = {"animal": Animal(), "dog": Dog()}[which]
                return [isinstance(obj, Animal), type(obj) is Animal]
            """,
            [("a dog", ["dog"]), ("an animal", ["animal"])],
            [("dog again", ["dog"]), ("animal again", ["animal"]),
             ("dog once more", ["dog"])],
            edges=[("base class", ["animal"])],
            difficulty="TUTORIAL", family="oop_typing", after="oopl-type-guided",
            starter="""
            class Animal:
                pass


            class Dog(Animal):
                pass


            def check_kinds(which):
                obj = {"animal": Animal(), "dog": Dog()}[which]
                # one isinstance check, one exact-type check
                pass
            """,
            nudge="Use `is` for the type comparison, not `==`. Classes are "
                  "singletons and identity is the intent.",
            pseudocode="return [isinstance(obj, Animal), type(obj) is Animal]",
            failures=["Writing `type(obj) == Animal`, which works and hides the "
                      "intent",
                      "Expecting isinstance to be False for a subclass"],
            tags=["isinstance", "type"],
        ),

        _oop(
            "oopl-bool-is-int-easy", "True Is An Integer",
            """
            `bool` is a subclass of `int`. So `isinstance(True, int)` is True, and
            any counting code that filters with `isinstance(v, int)` quietly counts
            your flags as numbers. This is the single most common way a type check
            goes wrong in real code.

            Return `[how many pass isinstance(v, int), how many pass
            type(v) is int]`.
            """,
            "int_counts", "values", _ref_int_counts,
            """
            def int_counts(values):
                loose = sum(1 for value in values if isinstance(value, int))
                # `is int` excludes bool, because bool is a different class that
                # merely inherits from int.
                strict = sum(1 for value in values if type(value) is int)
                return [loose, strict]
            """,
            [("flags and numbers", [[1, True, 2, False]]),
             ("numbers only", [[1, 2, 3]])],
            [("flags only", [[True, True]]), ("with strings", [[1, "1", True]]),
             ("with floats", [[1, 1.0, True]])],
            edges=[("empty", [[]]), ("none present", [["a", None]])],
            difficulty="EASY", family="oop_typing", after="oopl-isinstance-tutorial",
            starter="""
            def int_counts(values):
                # one count that accepts subclasses, one that does not
                pass
            """,
            nudge="`1.0` is a float and fails both checks. `True` passes exactly one "
                  "of them.",
            pseudocode="loose = count of isinstance(v, int)\n"
                       "strict = count of type(v) is int\nreturn [loose, strict]",
            failures=["Assuming the two counts are always equal",
                      "Filtering with `isinstance(v, (int, float))` and then being "
                      "surprised that booleans arrive in the arithmetic"],
            time="O(n)", tags=["isinstance", "type", "bool"],
        ),

        _oop(
            "oopl-abc-duck-medium", "The Contract And The Duck",
            """
            An abstract base class states a contract: declare a method
            `@abstractmethod` and the class cannot be instantiated until a subclass
            implements it. `TypeError`, at construction, not a mystery later.

            Duck typing is the other answer: an unrelated class with the same
            method works fine in the same code, because nothing ever checked.

            Write `Exporter` (abstract, with `render`), `CsvExporter` (joins with
            commas) and `DuckExporter` (no inheritance, joins with pipes).
            `export_report` returns `["ok", rendered]`, or `["error", "TypeError"]`
            if the class refused to be built.
            """,
            "export_report", "which, rows", _ref_export_report,
            """
            from abc import ABC, abstractmethod


            class Exporter(ABC):
                @abstractmethod
                def render(self, rows):
                    ...


            class CsvExporter(Exporter):
                def render(self, rows):
                    return ",".join(rows)


            class DuckExporter:
                # Inherits nothing, declares nothing, works anywhere `render` is
                # all that is actually asked for.
                def render(self, rows):
                    return "|".join(rows)


            def export_report(which, rows):
                chosen = {"abstract": Exporter, "csv": CsvExporter,
                          "duck": DuckExporter}[which]
                try:
                    exporter = chosen()
                except TypeError:
                    return ["error", "TypeError"]
                return ["ok", exporter.render(rows)]
            """,
            [("abstract refuses", ["abstract", ["a", "b"]]),
             ("csv", ["csv", ["a", "b"]])],
            [("duck", ["duck", ["a", "b", "c"]]), ("csv single", ["csv", ["only"]]),
             ("abstract with no rows", ["abstract", []])],
            edges=[("duck with no rows", ["duck", []]),
                   ("csv with no rows", ["csv", []])],
            difficulty="MEDIUM", family="oop_typing", after="oopl-bool-is-int-easy",
            starter="""
            from abc import ABC, abstractmethod


            class Exporter(ABC):
                @abstractmethod
                def render(self, rows):
                    ...


            class CsvExporter(Exporter):
                def render(self, rows):
                    pass


            class DuckExporter:
                def render(self, rows):
                    pass


            def export_report(which, rows):
                pass
            """,
            nudge="The TypeError arrives when you try to BUILD the abstract class, "
                  "not when you define it and not when you call render.",
            pseudocode="pick the class\ntry to instantiate\n"
                       "on TypeError return ['error', 'TypeError']\n"
                       "otherwise return ['ok', exporter.render(rows)]",
            failures=["Inheriting from ABC but forgetting @abstractmethod, which "
                      "makes the class instantiable and the contract decorative",
                      "Expecting DuckExporter to fail — nothing in this code ever "
                      "asks what class it is"],
            pattern="STRING", tags=["abc", "duck-typing", "isinstance"],
        ),

        # ==================================================================
        # 13. mutability and the default-argument trap
        # ==================================================================
        _oop(
            "oopl-default-guided", "The Safe Default",
            """
            A default argument is evaluated ONCE, when the `def` line runs. A
            mutable default is therefore one object shared by every call that does
            not pass its own — which is why the fix is always the same: default to
            `None` and build the real object inside.

            Fill in the default.
            """,
            "collect", "items", _ref_collect,
            """
            def add_item(item, bag=None):
                if bag is None:
                    bag = []
                bag.append(item)
                return bag


            def collect(items):
                # Each call passes no bag, so each call must get a fresh one.
                return [add_item(item) for item in items]
            """,
            [("three", [["a", "b", "c"]]), ("one", [["only"]])],
            [("numbers", [[1, 2]]), ("repeats", [["x", "x"]]),
             ("longer", [[1, 2, 3, 4, 5]])],
            edges=[("none at all", [[]])],
            difficulty="GUIDED", family="oop_mutability", after="oopl-abc-duck-medium",
            starter="""
            def add_item(item, bag=__BLANK__):
                # The sentinel goes in the signature; the real list is built here.
                if bag is None:
                    bag = []
                bag.append(item)
                return bag


            def collect(items):
                return [add_item(item) for item in items]
            """,
            nudge="`bag=[]` in the signature creates exactly one list, at import "
                  "time, and every caller shares it forever.",
            pseudocode="def add_item(item, bag=None):\n  if bag is None: bag = []",
            fragment=_same_move("def connect(host, options=None):\n    "
                                "options = options or {}"),
            failures=["`bag=[]`, which makes every result longer than the last",
                      "`if not bag:` instead of `if bag is None:`, which throws away "
                      "a legitimately empty list the caller passed on purpose"],
            tags=["mutable-default", "arguments"],
        ),

        _oop(
            "oopl-identity-tutorial", "Equal Is Not The Same As Same",
            """
            `==` asks whether two things have the same value. `is` asks whether
            they are the same object. Two lists built separately are equal and not
            identical; a name bound to an existing list is identical to it.

            Return `[a == b, a is b, a is alias]` where `b` is a separately built
            copy of `a` and `alias` is another name for `a`.
            """,
            "identity_report", "values", _ref_identity_report,
            """
            def identity_report(values):
                a = list(values)
                b = list(values)     # same contents, built separately
                alias = a            # not a copy: a second name for one object
                return [a == b, a is b, a is alias]
            """,
            [("numbers", [[1, 2, 3]]), ("strings", [["a"]])],
            [("empty", [[]]), ("nested", [[[1], [2]]]), ("mixed", [[1, "a", None]])],
            edges=[("single", [[0]])],
            difficulty="TUTORIAL", family="oop_mutability", after="oopl-default-guided",
            starter="""
            def identity_report(values):
                a = list(values)
                b = list(values)
                alias = a
                # equality, then identity, then identity through the alias
                pass
            """,
            nudge="Mutating `a` would change `alias` and leave `b` alone. That is "
                  "the whole difference, stated in one sentence.",
            pseudocode="return [a == b, a is b, a is alias]",
            failures=["Using `is` to compare values, which appears to work for small "
                      "integers and short strings because those are cached, and "
                      "then stops"],
            tags=["identity", "equality", "mutability"],
        ),

        _oop(
            "oopl-copy-easy", "Shallow Copies Share Their Insides",
            """
            `list(grid)` and `grid[:]` and `copy.copy(grid)` all make a new outer
            list holding the SAME inner lists. Change an inner list through the
            copy and the original changes with it. `copy.deepcopy` is what actually
            separates them.

            Take a shallow copy and a deep copy of `grid`, then write `value` to
            `shallow[0][0]` and to nothing else. Return
            `[shallow, deep, grid as it now stands]`.
            """,
            "copy_report", "grid, value", _ref_copy_report,
            """
            import copy


            def copy_report(grid, value):
                shallow = copy.copy(grid)      # new outer list, same inner rows
                deep = copy.deepcopy(grid)     # new everything, all the way down
                # One write, three lists. Two of them see it.
                shallow[0][0] = value
                return [shallow, deep, grid]
            """,
            [("two rows", [[[1, 2], [3, 4]], 9]),
             ("one row", [[[0]], 5])],
            [("wider", [[[1, 2, 3], [4, 5, 6]], 0]),
             ("negative value", [[[7, 7], [7, 7]], -1]),
             ("single column", [[[1], [2], [3]], 8])],
            edges=[("single cell", [[[1]], 2])],
            difficulty="EASY", family="oop_mutability", after="oopl-identity-tutorial",
            pattern="MATRIX",
            starter="""
            import copy


            def copy_report(grid, value):
                # take both copies BEFORE you write anything, then write once
                # through the shallow one, then report all three
                pass
            """,
            nudge="The deep copy is the only one that comes back unchanged, and "
                  "nothing was ever written through it. Work out why the original "
                  "moved.",
            pseudocode="shallow = copy.copy(grid)\ndeep = copy.deepcopy(grid)\n"
                       "shallow[0][0] = value\nreturn [shallow, deep, grid]",
            failures=["Expecting `grid` to be untouched — the shallow copy's row 0 "
                      "IS grid's row 0",
                      "Reaching for deepcopy everywhere out of fear, which is slow "
                      "and breaks on objects that cannot be copied"],
            time="O(n)", space="O(n)", tags=["copy", "mutability"],
        ),

        _oop(
            "oopl-mutable-dawn-medium", "Mutable Dawn",
            """
            She remembers every gift she was ever given. A function with
            `bag=[]` keeps that one list between calls, and the default lives on
            the function object itself as `__defaults__` — which is also how you
            can reset it, and how you can prove where it lives.

            Write both versions. `default_trap(items)` resets the broken function's
            default, then calls each version once per item, and returns
            `[results from the broken one, results from the fixed one]`.
            """,
            "default_trap", "items", _ref_default_trap,
            """
            def broken(item, bag=[]):
                bag.append(item)
                return list(bag)


            def fixed(item, bag=None):
                if bag is None:
                    bag = []
                bag.append(item)
                return list(bag)


            def default_trap(items):
                # The default is stored on the function, not recreated per call.
                # Resetting it here is what makes this function safe to run twice.
                broken.__defaults__ = ([],)
                return [[broken(item) for item in items],
                        [fixed(item) for item in items]]
            """,
            [("three gifts", [["a", "b", "c"]]), ("one gift", [["only"]])],
            [("numbers", [[1, 2]]), ("repeats", [["x", "x", "x"]]),
             ("longer", [[1, 2, 3, 4]])],
            edges=[("no gifts", [[]])],
            difficulty="MEDIUM", family="oop_mutability", after="oopl-copy-easy",
            starter="""
            def broken(item, bag=[]):
                bag.append(item)
                return list(bag)


            def fixed(item, bag=None):
                pass


            def default_trap(items):
                # reset broken.__defaults__ first, or the second test inherits
                # everything the first one appended
                pass
            """,
            nudge="`list(bag)` is not decoration: without it both functions return "
                  "the same list object over and over and the results all alias "
                  "each other.",
            pseudocode="broken.__defaults__ = ([],)\n"
                       "broken results grow: [a], [a,b], [a,b,c]\n"
                       "fixed results stay singletons",
            failures=["Returning `bag` itself, so every entry in the result is the "
                      "same object and shows the final state",
                      "Forgetting the reset, which makes the function pass once and "
                      "fail on the second test"],
            time="O(n)", tags=["mutable-default", "arguments"],
        ),

        # ==================================================================
        # 14. try / except / else / finally
        # ==================================================================
        _oop(
            "oopl-try-guided", "Catching One Named Thing",
            """
            `try` runs code that might fail. `except SomeError` catches exactly
            that failure and nothing else, which is the whole discipline: name what
            you can actually handle.

            Division by zero raises `ZeroDivisionError`. Name it.
            """,
            "safe_divide", "a, b", _ref_safe_divide,
            """
            def safe_divide(a, b):
                try:
                    return a / b
                except ZeroDivisionError:
                    return None
            """,
            [("normal", [10, 2]), ("by zero", [10, 0])],
            [("negative", [-9, 3]), ("zero numerator", [0, 5]),
             ("zero over zero", [0, 0])],
            edges=[("one over one", [1, 1])],
            difficulty="GUIDED", family="oop_exceptions",
            after="oopl-mutable-dawn-medium",
            starter="""
            def safe_divide(a, b):
                try:
                    return a / b
                except __BLANK__:
                    # only this failure, by name
                    return None
            """,
            nudge="A bare `except:` would also pass this test, and would also "
                  "swallow a typo in the line above it.",
            pseudocode="try: return a / b\nexcept ZeroDivisionError: return None",
            fragment=_same_move("except FileNotFoundError:\n    return default"),
            failures=["Catching `Exception`, which hides a TypeError from a bad "
                      "argument as though it were a division by zero",
                      "Checking `if b == 0` first — correct here, and it stops "
                      "scaling the moment the failure is not one comparison away"],
            tags=["exceptions", "try"],
        ),

        _oop(
            "oopl-except-order-tutorial", "Specific Before General",
            """
            Except clauses are tried top to bottom and the first match wins, so a
            broad one placed early shadows every specific one below it. Knowing the
            hierarchy is what makes the ordering obvious: `KeyError` and
            `IndexError` are both `LookupError`, and everything is `Exception`.

            Write `classify_error(kind)` returning "zero division", "lookup",
            "other", or "none" when nothing failed.
            """,
            "classify_error", "kind", _ref_classify_error,
            """
            def classify_error(kind):
                try:
                    if kind == "zero":
                        1 / 0
                    elif kind == "key":
                        {}["missing"]
                    elif kind == "index":
                        [][0]
                    elif kind == "type":
                        1 + "a"
                    return "none"
                except ZeroDivisionError:
                    return "zero division"
                except LookupError:
                    # KeyError and IndexError both live under this one.
                    return "lookup"
                except Exception:
                    return "other"
            """,
            [("a missing key", ["key"]), ("division", ["zero"])],
            [("an index", ["index"]), ("a type error", ["type"]),
             ("nothing wrong", ["clean"])],
            edges=[("clean path returns none", ["clean"])],
            difficulty="TUTORIAL", family="oop_exceptions", after="oopl-try-guided",
            starter="""
            def classify_error(kind):
                try:
                    if kind == "zero":
                        1 / 0
                    elif kind == "key":
                        {}["missing"]
                    elif kind == "index":
                        [][0]
                    elif kind == "type":
                        1 + "a"
                    return "none"
                except Exception:
                    pass
                # three except clauses, most specific first — replace this one
            """,
            nudge="Put `except Exception` first and the other two clauses become "
                  "unreachable code that Python will never warn you about.",
            pseudocode="except ZeroDivisionError -> 'zero division'\n"
                       "except LookupError -> 'lookup'\nexcept Exception -> 'other'",
            failures=["Listing `except Exception` before the specific clauses",
                      "Writing separate KeyError and IndexError clauses, which is "
                      "correct and says you have not met LookupError"],
            tags=["exceptions", "hierarchy"],
        ),

        _oop(
            "oopl-else-finally-easy", "Four Blocks, One Order",
            """
            The full statement has four parts and each has one job. `try` is the
            risky code. `except` runs only on a matching failure. `else` runs only
            when `try` finished without raising — it is where the "rest of the happy
            path" belongs, so it is not accidentally protected. `finally` runs
            either way, which is why cleanup lives there.

            Append the name of each block as it executes and return the trace,
            ending with "after".
            """,
            "trace_blocks", "kind", _ref_trace_blocks,
            """
            def trace_blocks(kind):
                order = []
                try:
                    order.append("try")
                    if kind == "boom":
                        raise ValueError("boom")
                except ValueError:
                    order.append("except")
                else:
                    # Only when nothing was raised.
                    order.append("else")
                finally:
                    # Always. Raised or not, returned or not.
                    order.append("finally")
                order.append("after")
                return order
            """,
            [("it raised", ["boom"]), ("it did not", ["quiet"])],
            [("quiet again", ["ok"]), ("boom again", ["boom"]),
             ("some other word", ["anything"])],
            edges=[("empty kind", [""])],
            difficulty="EASY", family="oop_exceptions",
            after="oopl-except-order-tutorial",
            starter="""
            def trace_blocks(kind):
                order = []
                # try / except ValueError / else / finally, appending each name,
                # then "after" once the whole statement is done
                pass
            """,
            nudge="`else` is not 'otherwise'. It is 'and nothing went wrong'.",
            pseudocode="boom  -> try, except, finally, after\n"
                       "quiet -> try, else, finally, after",
            failures=["Putting the else-block code at the end of `try`, where a "
                      "failure in it would be caught by your own except clause",
                      "Expecting `finally` to run before `except`"],
            tags=["exceptions", "finally", "else"],
        ),

        _oop(
            "oopl-finally-overrides-medium", "The Return That Ate The Exception",
            """
            A `return` inside `finally` wins over everything: over the value `try`
            was about to return, and over an exception on its way out. The exception
            is discarded silently. It is legal, it is almost never what anyone
            wants, and it is worth being able to explain.

            `attempt(kind)` has all three paths. `finally_report` wraps it and
            returns `["returned", value]` or `["raised", exception name]`.
            """,
            "finally_report", "kind", _ref_finally_report,
            """
            def attempt(kind):
                try:
                    if kind in ("caught", "swallowed"):
                        raise ValueError("boom")
                    if kind == "escapes":
                        raise TypeError("wrong shape")
                    return "try"
                except ValueError:
                    return "except"
                finally:
                    if kind == "swallowed":
                        # This return discards the ValueError entirely.
                        return "finally"


            def finally_report(kind):
                try:
                    return ["returned", attempt(kind)]
                except TypeError:
                    return ["raised", "TypeError"]
            """,
            [("swallowed by finally", ["swallowed"]), ("plain return", ["plain"])],
            [("caught", ["caught"]), ("escapes", ["escapes"]),
             ("plain again", ["plain"])],
            edges=[("caught again", ["caught"])],
            difficulty="MEDIUM", family="oop_exceptions",
            after="oopl-else-finally-easy",
            starter="""
            def attempt(kind):
                try:
                    # raise ValueError for "caught" and "swallowed"
                    # raise TypeError for "escapes"
                    # otherwise return "try"
                    pass
                except ValueError:
                    return "except"
                finally:
                    # return "finally" only for kind == "swallowed"
                    pass


            def finally_report(kind):
                pass
            """,
            nudge="For \"swallowed\" the except clause genuinely returns 'except' "
                  "first — and then `finally` returns, and that return replaces it.",
            pseudocode="plain     -> ['returned', 'try']\n"
                       "caught    -> ['returned', 'except']\n"
                       "swallowed -> ['returned', 'finally']\n"
                       "escapes   -> ['raised', 'TypeError']",
            failures=["Expecting the TypeError to be swallowed too — the finally "
                      "block only returns for one specific kind",
                      "Putting a bare `return` in `finally` unconditionally, which "
                      "makes every failure in the function invisible"],
            tags=["exceptions", "finally"],
        ),

        # ==================================================================
        # 15. custom exceptions and raise from
        # ==================================================================
        _oop(
            "oopl-custom-exc-guided", "An Error Of Your Own",
            """
            A custom exception is one line: a class inheriting from `Exception`.
            Its value is that callers can catch YOUR failure without catching
            everything that happens to fail nearby.

            Fill in the base class.
            """,
            "load_setting", "settings, key", _ref_load_setting,
            """
            class ConfigError(Exception):
                pass


            def load_setting(settings, key):
                try:
                    if key not in settings:
                        raise ConfigError("missing setting: " + key)
                    return ["ok", settings[key]]
                except ConfigError as exc:
                    return ["error", str(exc)]
            """,
            [("present", [{"port": "8080"}, "port"]),
             ("absent", [{"port": "8080"}, "host"])],
            [("empty settings", [{}, "anything"]),
             ("two keys", [{"a": "1", "b": "2"}, "b"]),
             ("empty key name", [{"": "blank"}, ""])],
            edges=[("value is empty", [{"k": ""}, "k"])],
            difficulty="GUIDED", family="oop_custom_exc",
            after="oopl-finally-overrides-medium", pattern="HASH_MAP",
            starter="""
            class ConfigError(__BLANK__):
                # Inherit from the right base and you get args, str() and
                # tracebacks for free.
                pass


            def load_setting(settings, key):
                try:
                    if key not in settings:
                        raise ConfigError("missing setting: " + key)
                    return ["ok", settings[key]]
                except ConfigError as exc:
                    return ["error", str(exc)]
            """,
            nudge="Inherit from `Exception`, not from `BaseException`. The latter is "
                  "reserved for things that should not be caught by ordinary "
                  "handlers, like KeyboardInterrupt.",
            pseudocode="class ConfigError(Exception): pass",
            fragment=_same_move("class RateLimited(Exception):\n    pass"),
            failures=["Inheriting from BaseException, which makes `except Exception` "
                      "miss it",
                      "Raising the class without a message, which gives a traceback "
                      "that says nothing"],
            tags=["exceptions", "custom"],
        ),

        _oop(
            "oopl-exc-hierarchy-tutorial", "One Base, Several Failures",
            """
            Give your errors a shared base and callers get a choice: catch the
            specific one when they can fix it, or catch the base when they only
            need to know that your subsystem failed.

            Build `VaultError(Exception)` with `LockedError` and `EmptyError` under
            it. Catch the base and report `["vault", the class name]`; catch
            anything else as `["other", the class name]`.
            """,
            "open_vault", "state", _ref_open_vault,
            """
            class VaultError(Exception):
                pass


            class LockedError(VaultError):
                pass


            class EmptyError(VaultError):
                pass


            def open_vault(state):
                try:
                    if state == "locked":
                        raise LockedError("locked")
                    if state == "empty":
                        raise EmptyError("empty")
                    if state == "cursed":
                        raise RuntimeError("cursed")
                    return ["ok", state]
                except VaultError as exc:
                    # One clause, both subclasses, exact name preserved.
                    return ["vault", type(exc).__name__]
                except Exception as exc:
                    return ["other", type(exc).__name__]
            """,
            [("locked", ["locked"]), ("cursed", ["cursed"])],
            [("empty", ["empty"]), ("open", ["open"]), ("locked again", ["locked"])],
            edges=[("nothing wrong", ["open"])],
            difficulty="TUTORIAL", family="oop_custom_exc",
            after="oopl-custom-exc-guided",
            starter="""
            class VaultError(Exception):
                pass


            class LockedError(VaultError):
                pass


            class EmptyError(VaultError):
                pass


            def open_vault(state):
                # raise the right error per state, then catch the base first
                pass
            """,
            nudge="`type(exc).__name__` still gives you the specific class even "
                  "though you caught the base. Catching broadly does not erase "
                  "which one it was.",
            pseudocode="except VaultError -> ['vault', class name]\n"
                       "except Exception -> ['other', class name]",
            failures=["Catching `Exception` before `VaultError`, which makes every "
                      "vault failure report as 'other'",
                      "Making LockedError inherit from Exception directly, which "
                      "removes the point of the base"],
            tags=["exceptions", "custom", "hierarchy"],
        ),

        _oop(
            "oopl-raise-from-easy", "Translating A Failure",
            """
            Low-level errors leaking out of a library are a design smell: the
            caller should not have to know you used `int()`. Translate it into your
            own error, and use `raise YourError(...) from exc` so the original is
            kept as `__cause__` and still appears in the traceback.

            `parse_port` raises `ParseError("bad port: <text>") from` the ValueError.
            `port_report` returns `["ok", value]` or
            `["error", message, name of the cause]`.
            """,
            "port_report", "text", _ref_port_report,
            """
            class ParseError(Exception):
                pass


            def parse_port(text):
                try:
                    return int(text)
                except ValueError as exc:
                    # `from exc` keeps the original. Losing it is how a five-minute
                    # bug becomes an afternoon.
                    raise ParseError("bad port: " + text) from exc


            def port_report(text):
                try:
                    return ["ok", parse_port(text)]
                except ParseError as exc:
                    return ["error", str(exc), type(exc.__cause__).__name__]
            """,
            [("a port", ["8080"]), ("not a number", ["eighty"])],
            [("negative", ["-1"]), ("empty", [""]), ("trailing letter", ["80a"])],
            edges=[("zero", ["0"]), ("plus sign", ["+80"])],
            difficulty="EASY", family="oop_custom_exc",
            after="oopl-exc-hierarchy-tutorial",
            starter="""
            class ParseError(Exception):
                pass


            def parse_port(text):
                # int(text), and translate ValueError into ParseError ... from exc
                pass


            def port_report(text):
                pass
            """,
            nudge="`raise ... from exc` sets `__cause__`. Plain `raise ...` inside "
                  "an except block sets `__context__` instead, which prints as "
                  "'during handling of the above' and is easier to miss.",
            pseudocode="try: return int(text)\nexcept ValueError as exc:\n"
                       "  raise ParseError('bad port: ' + text) from exc",
            failures=["`raise ParseError(...) from None`, which deliberately hides "
                      "the cause — occasionally right, usually a mistake",
                      "Catching the ValueError and returning a sentinel, which "
                      "pushes the failure to whoever forgets to check"],
            pattern="STRING", tags=["exceptions", "raise-from", "custom"],
        ),

        # ==================================================================
        # 16. catching narrowly
        # ==================================================================
        _oop(
            "oopl-narrow-guided", "Catch What You Can Handle",
            """
            `int(value)` fails two different ways: `ValueError` when the text is
            not a number, `TypeError` when the thing is not text at all. Both are
            recoverable here, so name both — as a tuple.

            Fill in the tuple of exceptions.
            """,
            "parse_all", "values", _ref_parse_all,
            """
            def parse_all(values):
                out = []
                for value in values:
                    try:
                        out.append(int(value))
                    except (ValueError, TypeError):
                        out.append(None)
                return out
            """,
            [("mixed", [["12", 3, "x", None]]), ("all good", [["1", "2"]])],
            [("floats truncate", [[4.9]]), ("booleans are ints", [[True, False]]),
             ("empty string", [[""]])],
            edges=[("nothing to parse", [[]]), ("all bad", [[None, "no"]])],
            difficulty="GUIDED", family="oop_narrow_except",
            after="oopl-raise-from-easy",
            starter="""
            def parse_all(values):
                out = []
                for value in values:
                    try:
                        out.append(int(value))
                    except __BLANK__:
                        # both recoverable failures, named as a tuple
                        out.append(None)
                return out
            """,
            nudge="One except clause can name several exceptions: "
                  "`except (A, B):`. The parentheses are required.",
            pseudocode="except (ValueError, TypeError): out.append(None)",
            fragment=_same_move("except (KeyError, IndexError):\n    return default"),
            failures=["`except ValueError, TypeError:` — that is Python 2 and it is "
                      "a syntax error now",
                      "Catching `Exception` and turning a genuine bug into a None"],
            time="O(n)", tags=["exceptions", "narrow"],
        ),

        _oop(
            "oopl-bare-except-tutorial", "What A Bare except Would Also Take",
            """
            `except Exception` does NOT catch `SystemExit` or `KeyboardInterrupt`,
            because those are `BaseException` and are not errors — they are someone
            asking the program to stop. A bare `except:` catches them anyway, which
            is why a bare except can make a program you cannot Ctrl-C out of.

            `guarded(kind)` catches `Exception`. Return `["returned", value]`, or
            `["escaped", "SystemExit"]` if it got past.
            """,
            "guard_report", "kind", _ref_guard_report,
            """
            def guarded(kind):
                try:
                    if kind == "value":
                        raise ValueError("ordinary failure")
                    if kind == "exit":
                        raise SystemExit(3)
                    return "clean"
                except Exception:
                    # SystemExit is not an Exception, so it walks straight through.
                    return "caught"


            def guard_report(kind):
                try:
                    return ["returned", guarded(kind)]
                except SystemExit:
                    return ["escaped", "SystemExit"]
            """,
            [("an ordinary error", ["value"]), ("an exit request", ["exit"])],
            [("nothing raised", ["clean"]), ("exit again", ["exit"]),
             ("value again", ["value"])],
            edges=[("unknown kind is clean", ["other"])],
            difficulty="TUTORIAL", family="oop_narrow_except",
            after="oopl-narrow-guided",
            starter="""
            def guarded(kind):
                try:
                    # raise ValueError for "value", SystemExit(3) for "exit",
                    # otherwise return "clean"
                    pass
                except Exception:
                    return "caught"


            def guard_report(kind):
                pass
            """,
            nudge="The hierarchy: BaseException at the top, then Exception, and "
                  "SystemExit / KeyboardInterrupt / GeneratorExit sit beside "
                  "Exception rather than under it.",
            pseudocode="value -> ['returned', 'caught']\n"
                       "exit  -> ['escaped', 'SystemExit']\n"
                       "clean -> ['returned', 'clean']",
            failures=["Expecting `except Exception` to catch SystemExit",
                      "Using a bare `except:` to be safe, which is the exact "
                      "opposite of safe"],
            tags=["exceptions", "narrow", "bare-except"],
        ),

        _oop(
            "oopl-reraise-easy", "Note It, Then Let It Go",
            """
            Sometimes the right handling is: record that it happened, then re-raise
            so whoever can actually fix it still hears about it. A bare `raise`
            inside an except block re-raises the SAME exception with its original
            traceback intact — `raise exc` would work too and truncates less
            usefully.

            `audit(source, key)` returns `["ok", value, log]` on a hit, and
            `["error", "KeyError", log]` when the key is missing, with the log
            holding `"missing:<key>"`.
            """,
            "audit", "source, key", _ref_audit,
            """
            def audit(source, key):
                log = []
                try:
                    try:
                        return ["ok", source[key], log]
                    except KeyError:
                        log.append("missing:" + key)
                        raise            # same exception, same traceback
                except KeyError as exc:
                    return ["error", type(exc).__name__, log]
            """,
            [("hit", [{"a": 1}, "a"]), ("miss", [{"a": 1}, "b"])],
            [("empty source", [{}, "x"]), ("value is none", [{"k": None}, "k"]),
             ("two keys", [{"a": 1, "b": 2}, "b"])],
            edges=[("empty key", [{"": 0}, ""])],
            difficulty="EASY", family="oop_narrow_except",
            after="oopl-bare-except-tutorial", pattern="HASH_MAP",
            starter="""
            def audit(source, key):
                log = []
                # inner try: look the key up
                # on KeyError: record it, then re-raise with a bare `raise`
                # outer try: catch it and report
                pass
            """,
            nudge="A bare `raise` only works inside an except block. Outside one it "
                  "raises RuntimeError because there is nothing to re-raise.",
            pseudocode="inner: return ['ok', source[key], log]\n"
                       "except KeyError: log it, bare raise\n"
                       "outer except KeyError: return ['error', name, log]",
            failures=["Swallowing the KeyError after logging, so the caller gets a "
                      "success it did not earn",
                      "Using `source.get(key)` and losing the distinction between "
                      "a missing key and a stored None"],
            tags=["exceptions", "reraise"],
        ),

        # ==================================================================
        # 17. __slots__
        # ==================================================================
        _oop(
            "oopl-slots-guided", "Declaring The Attributes Up Front",
            """
            `__slots__` names the attributes a class is allowed to have. Python
            then stores them in a fixed array instead of a per-instance dict, which
            is a real memory saving when you make millions of small objects.

            Fill in the declaration.
            """,
            "pixel_fields", "x, y", _ref_pixel_fields,
            """
            class Pixel:
                __slots__ = ("x", "y")

                def __init__(self, x, y):
                    self.x = x
                    self.y = y


            def pixel_fields(x, y):
                pixel = Pixel(x, y)
                return [pixel.x, pixel.y, list(Pixel.__slots__)]
            """,
            [("origin", [0, 0]), ("a point", [3, 4])],
            [("negative", [-1, -2]), ("large", [1920, 1080]), ("mixed", [0, 7])],
            edges=[("both zero", [0, 0])],
            difficulty="GUIDED", family="oop_slots", after="oopl-reraise-easy",
            starter="""
            class Pixel:
                # Name the two attributes this class is allowed to have.
                __slots__ = __BLANK__

                def __init__(self, x, y):
                    self.x = x
                    self.y = y


            def pixel_fields(x, y):
                pixel = Pixel(x, y)
                return [pixel.x, pixel.y, list(Pixel.__slots__)]
            """,
            nudge="A tuple of strings, in the order you want them. `__slots__ = "
                  "\"x\"` is a string, and a string is a sequence of characters, "
                  "which is not what you meant.",
            pseudocode='__slots__ = ("x", "y")',
            fragment=_same_move('__slots__ = ("row", "col")'),
            failures=["Writing `__slots__ = ('x')`, which is just the string 'x'",
                      "Also assigning a class-level default with the same name, "
                      "which collides with the slot"],
            tags=["slots", "memory"],
        ),

        _oop(
            "oopl-slots-reject-tutorial", "The Attribute That Will Not Stick",
            """
            The price of `__slots__` is that undeclared attributes are refused with
            `AttributeError`. That is usually a feature — a typo'd attribute name
            normally creates a new attribute in silence, and here it cannot.

            Try `setattr(pixel, name, 9)` and return `["assigned", name]` or
            `["refused", name]`.
            """,
            "slots_report", "name", _ref_slots_report,
            """
            class Pixel:
                __slots__ = ("x", "y")

                def __init__(self, x, y):
                    self.x = x
                    self.y = y


            def slots_report(name):
                pixel = Pixel(1, 2)
                try:
                    setattr(pixel, name, 9)
                    return ["assigned", name]
                except AttributeError:
                    # Not in __slots__, and there is no __dict__ to fall back on.
                    return ["refused", name]
            """,
            [("declared", ["x"]), ("a typo", ["z"])],
            [("the other slot", ["y"]), ("a plausible name", ["colour"]),
             ("near miss", ["xx"])],
            edges=[("empty name", [""])],
            difficulty="TUTORIAL", family="oop_slots", after="oopl-slots-guided",
            starter="""
            class Pixel:
                __slots__ = ("x", "y")

                def __init__(self, x, y):
                    self.x = x
                    self.y = y


            def slots_report(name):
                pixel = Pixel(1, 2)
                # try the assignment, catch AttributeError
                pass
            """,
            nudge="Catch `AttributeError` specifically. It is the only failure this "
                  "code can produce, and naming it documents that.",
            pseudocode="try: setattr(pixel, name, 9); return ['assigned', name]\n"
                       "except AttributeError: return ['refused', name]",
            failures=["Expecting a NameError or a TypeError",
                      "Using `pixel.name = 9`, which sets an attribute literally "
                      "called 'name'"],
            tags=["slots", "attribute-error"],
        ),

        _oop(
            "oopl-slots-dict-easy", "Where The Attributes Actually Live",
            """
            An ordinary instance keeps its attributes in `__dict__`. A slotted one
            does not have a `__dict__` at all — that absence IS the memory saving.

            And the catch worth knowing: a subclass that does not declare its own
            `__slots__` gets a `__dict__` back, which quietly undoes the whole
            thing.

            Return `[whether the object has a __dict__, obj.a]`.
            """,
            "dict_report", "which", _ref_dict_report,
            """
            class Plain:
                def __init__(self):
                    self.a = 1


            class Slotted:
                __slots__ = ("a",)

                def __init__(self):
                    self.a = 1


            class SlottedChild(Slotted):
                # No __slots__ here, so instances get a __dict__ after all.
                pass


            def dict_report(which):
                obj = {"plain": Plain(), "slotted": Slotted(),
                       "child": SlottedChild()}[which]
                return [hasattr(obj, "__dict__"), obj.a]
            """,
            [("slotted", ["slotted"]), ("the subclass", ["child"])],
            [("plain", ["plain"]), ("slotted again", ["slotted"]),
             ("child again", ["child"])],
            edges=[("plain again", ["plain"])],
            difficulty="EASY", family="oop_slots", after="oopl-slots-reject-tutorial",
            starter="""
            class Plain:
                def __init__(self):
                    self.a = 1


            class Slotted:
                __slots__ = ("a",)

                def __init__(self):
                    self.a = 1


            class SlottedChild(Slotted):
                pass


            def dict_report(which):
                pass
            """,
            nudge="`SlottedChild` still cannot be given arbitrary attributes on the "
                  "parent's slots — but it can be given arbitrary NEW ones, because "
                  "it has a dict of its own.",
            pseudocode="plain   -> [True, 1]\nslotted -> [False, 1]\n"
                       "child   -> [True, 1]",
            failures=["Assuming __slots__ is inherited as a restriction",
                      "Reaching for __slots__ as a speed optimisation — it is a "
                      "memory one, and only at scale"],
            tags=["slots", "memory", "inheritance"],
        ),

        # ==================================================================
        # 18. the GIL, in plain language
        # ==================================================================
        _oop(
            "oopl-gil-guided", "Threads Wait Well, They Do Not Compute Well",
            """
            One sentence: the Global Interpreter Lock means only one thread runs
            Python bytecode at a time in a single process.

            What follows from it is the whole practical answer. Work that WAITS —
            network, disk, a database — releases the lock while it waits, so
            threads help a lot. Work that COMPUTES holds the lock, so extra threads
            buy nothing and you want separate processes.

            Fill in the answer for CPU-bound work.
            """,
            "pick_executor", "workload", _ref_pick_executor,
            """
            def pick_executor(workload):
                # CPU-bound work fights over the one lock; give it its own process.
                if workload == "cpu":
                    return "processes"
                # Everything else here is waiting, and waiting releases the lock.
                return "threads"
            """,
            [("number crunching", ["cpu"]), ("http calls", ["network"])],
            [("disk reads", ["disk"]), ("database", ["database"]),
             ("cpu again", ["cpu"])],
            edges=[("unrecognised workload defaults to threads", ["unknown"])],
            difficulty="GUIDED", family="oop_gil", after="oopl-slots-dict-easy",
            pattern="STRING",
            starter="""
            def pick_executor(workload):
                if workload == "cpu":
                    # Only one thread can run bytecode at a time. Which pool?
                    return __BLANK__
                return "threads"
            """,
            nudge="The GIL is per process. Two processes have two of them.",
            pseudocode='cpu -> "processes"\neverything else -> "threads"',
            fragment=_same_move('pool = ProcessPoolExecutor() if cpu_bound '
                                'else ThreadPoolExecutor()'),
            failures=["Saying threads are useless in Python — they are excellent "
                      "for the waiting that most services spend their life doing",
                      "Saying the GIL makes Python thread-safe, which it does not"],
            tags=["gil", "threading", "concurrency"],
        ),

        _oop(
            "oopl-gil-lock-tutorial", "The Lock You Still Need",
            """
            The GIL does not make your code thread-safe. It guarantees one
            bytecode at a time, and `total += 1` is several bytecodes: read, add,
            store. A thread can be switched out between them, and the increment is
            lost.

            So you take a lock. Write `locked_total` using `threading.Lock` so the
            answer is exactly `threads * per_thread`, every time.
            """,
            "locked_total", "threads, per_thread", _ref_locked_total,
            """
            import threading


            def locked_total(threads, per_thread):
                state = {"value": 0}
                lock = threading.Lock()

                def worker():
                    for _ in range(per_thread):
                        # `with lock:` acquires and always releases, even on an
                        # exception. Hand-rolled acquire/release does not.
                        with lock:
                            state["value"] += 1

                workers = [threading.Thread(target=worker) for _ in range(threads)]
                for thread in workers:
                    thread.start()
                for thread in workers:
                    thread.join()
                return state["value"]
            """,
            [("four threads", [4, 250]), ("two threads", [2, 100])],
            [("one thread", [1, 500]), ("eight threads", [8, 100]),
             ("tiny", [3, 1])],
            edges=[("no threads", [0, 100]), ("no work", [4, 0])],
            difficulty="TUTORIAL", family="oop_gil", after="oopl-gil-guided",
            starter="""
            import threading


            def locked_total(threads, per_thread):
                state = {"value": 0}
                lock = threading.Lock()

                def worker():
                    # increment per_thread times, holding the lock each time
                    pass

                # build the threads, start them all, then join them all
                pass
            """,
            nudge="Start every thread before you join any of them. Starting and "
                  "joining in the same loop runs them one after another.",
            pseudocode="lock = threading.Lock()\nworker: for each step: with lock: "
                       "value += 1\nstart all threads, then join all threads",
            failures=["Joining inside the start loop, which is just a slow sequential "
                      "run",
                      "Using a plain integer in the enclosing scope without "
                      "`nonlocal`, which raises UnboundLocalError"],
            time="O(n)", tags=["gil", "threading", "lock"],
        ),

        mcq_problem(
            id="oopl-gil-explain-easy",
            title="What The Lock Actually Promises",
            realm="fields_of_syntax", pattern="SIMULATION", difficulty="EASY",
            statement="""
            An interviewer asks you to explain the GIL. Which statement is the
            accurate one?
            """,
            choices=[
                "It prevents two threads from running Python bytecode at the same "
                "time in one process, so CPU-bound work gains nothing from threads "
                "while IO-bound work still does.",
                "It makes all Python operations atomic, so you never need a lock of "
                "your own.",
                "It stops you from creating more than one thread per process.",
                "It applies across every Python process on the machine, so "
                "multiprocessing does not help either.",
            ],
            answer=0,
            explanation="""
            The lock is per interpreter, per process, and it is about bytecode
            execution. Two consequences follow and both get asked about.

            First: threads still help enormously with waiting, because a socket
            read or a disk read releases the lock while it blocks. Most services
            spend their lives waiting.

            Second: it is not a substitute for your own locks. `total += 1`
            compiles to several bytecodes and a thread switch can land in the
            middle of them, so shared mutable state still needs a `threading.Lock`.

            For CPU-bound work the answer is separate processes — each one gets its
            own interpreter and its own lock — or a library that releases the lock
            while it works in C.
            """,
            family="oop_gil", seconds=90,
            distractor_notes={
                "1": "Atomicity is exactly what the GIL does not give you at the "
                     "level of your own statements.",
                "2": "Threads are unlimited; what is limited is how many run "
                     "bytecode at once.",
                "3": "Each process has its own interpreter and its own lock, which "
                     "is the entire reason multiprocessing is the CPU-bound answer.",
            },
        ),
    ]
