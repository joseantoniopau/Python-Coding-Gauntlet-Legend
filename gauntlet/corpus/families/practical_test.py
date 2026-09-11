"""The Practical Test: data, files, text, and somebody else's codebase.

Every other family in this corpus asks for an algorithm on a blank screen. The
practical exercise this player is preparing for does not look like that. It
hands over an existing codebase and asks them to navigate it, add functionality
to it, and fix a bug in it — with the tests that were already there still
passing at the end.

So these problems are shaped like work. A log file with one malformed line in
it. A CSV that has to come out the other side as a report. Config layers that
merge in a defined order. A regex that has to hold, and one question about when
a regex is the wrong tool entirely. Timestamps in three formats. And then the
four encounters that matter most, because they are the reported format: add a
feature to a module you did not write, find and fix a bug in a module you did
not write, extend somebody else's class, and refactor without changing
behaviour.

The given modules are deliberately imperfect. There is a stale comment, a helper
nobody calls any more, a name that was chosen on a Friday. Real code looks like
that, and reading past it is most of the skill.

Every topic enters at GUIDED — one expression typed into an otherwise finished
function — then TUTORIAL, then EASY, before it is allowed to be hard. A topic
that first appears at MEDIUM would be a bug in this file.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from ._base import (code_problem, debug_problem, dedent, design_problem,
                    mcq_problem)
from .scaffolds import _blank, rune

# Profile weights. The practical exercise is the reported shape of the on-site,
# so it is weighted heavily for every profile rather than treated as a side dish.
W = {"PRACTICAL": 2.5, "GENERAL_SWE": 2.5, "SECURITY_ENGINEERING": 2.5}

VIZ = {"type": "array_scan", "caption": "One pass over real, dirty data."}

# Appended to every give-them-a-module encounter. Without it the player reads the
# whole file hunting for a second thing to fix, which is not the exercise.
GIVEN_NOTE = (
    "\nThe module below is yours to edit. It works today and its existing "
    "behaviour is covered by the visible tests — if you break one of those, you "
    "have broken something that already shipped."
)


def work(pid, title, statement, fn, params, ref, canonical, visible, hidden, *,
         edges=(), difficulty="EASY", pattern="STRING", family="practical",
         realm="fields_of_syntax", nudge="", visual="", pseudocode="",
         failures=(), constraints=(), time="O(n)", space="O(n)", cmp="exact",
         tags=(), encounter="CODE_BATTLE", starter_code="", starter_hint="",
         secondary=(), viz=None, source_type="GENERAL_INTERVIEW", provenance=""):
    """One practical problem. The same twenty-line shape as every other family."""
    return code_problem(
        id=pid, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        statement=statement, fn_name=fn, params=params, reference=ref,
        canonical=canonical, visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        time_complexity=time, space_complexity=space, family=family,
        constraints=list(constraints), failures=list(failures),
        nudge=nudge or "Read the input format twice before you write anything.",
        visual=visual or "Take one real input line and say out loud what it "
                         "should become. Then write only that.",
        pseudocode=pseudocode, profile_weight=W, viz=viz or VIZ,
        tags=["practical"] + list(tags), encounter=encounter,
        starter_code=starter_code, starter_hint=starter_hint,
        secondary=list(secondary), source_type=source_type, provenance=provenance,
    )


def guided(pid, title, statement, fn, params, ref, canonical, blanks, visible,
           hidden, *, edges=(), pattern="STRING", family="practical",
           realm="fields_of_syntax", scaffold_for="", nudge="", visual="",
           constraints=(), failures=(), time="O(n)", space="O(n)", cmp="exact",
           tags=()):
    """The first rung of every topic here: the function is finished except for
    one expression, and that expression is the idea."""
    return rune(
        id=pid, title=title, realm=realm, difficulty="GUIDED", pattern=pattern,
        family=family, scaffold_for=scaffold_for or title, statement=statement,
        fn_name=fn, params=params, reference=ref, canonical=canonical,
        blanks=blanks, visible=visible, hidden=hidden, edges=edges, cmp=cmp,
        time_complexity=time, space_complexity=space,
        constraints=list(constraints), failures=list(failures),
        nudge=nudge or "The surrounding lines already tell you what the missing "
                       "expression has to produce.",
        visual=visual or "Read the line above the blank and the line below it. "
                         "The blank is whatever turns one into the other.",
        tags=["practical"] + list(tags),
    )


def extend_class(pid, title, statement, cls_name, reference_cls, canonical,
                 starter, visible, hidden, *, edges=(), difficulty="EASY",
                 realm="coding_coliseum", family="design", nudge="", visual="",
                 pseudocode="", failures=(), constraints=(), tags=(), blanks=()):
    """Extend a class somebody else wrote.

    `design_problem` generates an empty `class X: ...` starter, which is right
    for design-from-scratch and wrong here: the whole encounter is that the
    class already exists and you did not write it. The starter is therefore the
    given module, set after construction — the one field the builder has no
    parameter for.

    At GUIDED, pass `blanks` instead of `starter` and the scaffold is struck out
    of the canonical solution by the same `_blank` the Rune Vault uses, so the
    holes can never drift away from the answer they teach.
    """
    problem = design_problem(
        id=pid, title=title, realm=realm, difficulty=difficulty,
        statement=statement + GIVEN_NOTE, cls_name=cls_name,
        reference_cls=reference_cls, canonical=canonical, visible=visible,
        hidden=hidden, edges=edges, constraints=list(constraints),
        failures=list(failures), nudge=nudge or "Find the method that already does "
                                                "most of this and follow its lead.",
        visual=visual or "Which existing attribute already holds what the new "
                         "method needs? Add a second structure only if none does.",
        pseudocode=pseudocode, family=family, profile_weight=W, viz=VIZ,
        tags=["practical", "given-codebase"] + list(tags),
    )
    problem.starter_code = (_blank(dedent(canonical), blanks) if blanks
                            else dedent(starter))
    return problem


# ---------------------------------------------------------------------------
# 1. A log file, and a question about it
# ---------------------------------------------------------------------------
#
# Format used throughout this section:
#   2026-03-10 09:14:02 ERROR api GET /v1/session 500 118
#   date       time     level service method path status ms

APP_LOG = [
    "2026-03-10 09:14:02 INFO api GET /v1/session 200 12",
    "2026-03-10 09:14:03 ERROR api POST /v1/login 500 118",
    "2026-03-10 09:14:59 WARN cache GET /v1/keys 404 3",
    "2026-03-10 09:15:01 ERROR api POST /v1/login 503 202",
    "2026-03-10 09:15:44 INFO api GET /v1/session 200 9",
]

# The line that punishes a substring test: the word ERROR is in the message.
DECOY_LOG = APP_LOG + ["2026-03-10 09:16:00 INFO api GET /v1/health 200 4 ERROR"]


def _ref_count_errors(lines):
    return len([line for line in lines if line.split()[2:3] == ["ERROR"]])


def _ref_level_counts(lines):
    counts = {}
    for line in lines:
        fields = line.split()
        if len(fields) < 3:
            continue
        counts[fields[2]] = counts.get(fields[2], 0) + 1
    return counts


def _ref_worst_path(lines):
    failures = {}
    for line in lines:
        fields = line.split()
        if len(fields) < 7:
            continue
        try:
            status = int(fields[6])
        except ValueError:
            continue
        if status >= 500:
            failures[fields[5]] = failures.get(fields[5], 0) + 1
    if not failures:
        return ""
    best = min(failures.items(), key=lambda item: (-item[1], item[0]))
    return best[0]


def _ref_errors_per_minute(lines):
    buckets = {}
    for line in lines:
        fields = line.split()
        if len(fields) < 3 or fields[2] != "ERROR":
            continue
        minute = fields[0] + " " + fields[1][:5]
        buckets[minute] = buckets.get(minute, 0) + 1
    return [[minute, buckets[minute]] for minute in sorted(buckets)]


def _ref_sessions(lines):
    open_at, done = {}, []
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            continue
        stamp = fields[0] + " " + fields[1]
        try:
            moment = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        user, action = fields[2], fields[3]
        if action == "login":
            open_at[user] = moment
        elif action == "logout" and user in open_at:
            done.append([user, int((moment - open_at.pop(user)).total_seconds())])
    done.sort(key=lambda pair: (pair[0], pair[1]))
    return done


SESSION_LOG = [
    "2026-03-10 09:00:00 alice login",
    "2026-03-10 09:00:30 bob login",
    "2026-03-10 09:05:00 alice logout",
    "2026-03-10 09:06:00 carol logout",
    "2026-03-10 09:10:00 bob logout",
]


def logs() -> list:
    return [
        guided(
            "pt-log-count-errors", "The Third Field",
            "`lines` are log lines. The level is the THIRD whitespace-separated "
            "field. Count the lines whose level is ERROR.\n\n"
            "One of the test inputs mentions the word ERROR inside the message of "
            "an INFO line. It does not count. That is the whole reason you look at "
            "a field instead of searching the line.",
            "count_errors", "lines", _ref_count_errors,
            """
            def count_errors(lines):
                total = 0
                for line in lines:
                    fields = line.split()
                    if len(fields) >= 3 and fields[2] == "ERROR":
                        total += 1
                return total
            """,
            [('fields[2] == "ERROR"',
              "the level lives at index 2 — compare it, do not search the line")],
            [("five lines", [APP_LOG]), ("decoy in the message", [DECOY_LOG])],
            [("all clean", [[APP_LOG[0], APP_LOG[4]]]),
             ("short line is not a crash", [["2026-03-10 09:14:02"]])],
            edges=[("no lines", [[]])],
            pattern="STRING", family="log_parsing", realm="stringwood_labyrinth",
            scaffold_for="COUNTING BY FIELD, NOT BY SUBSTRING",
            failures=["`'ERROR' in line` also matches the word in a message",
                      "Indexing `fields[2]` before checking the line has three fields"],
            nudge="`line.split()` already gave you the fields. Which index is the level?",
        ),

        work("pt-log-level-counts", "Tally of the Watch",
             "Return a dict mapping each log level to the number of lines carrying "
             "it. The level is the third whitespace-separated field. A line with "
             "fewer than three fields is skipped, not counted and not fatal.",
             "level_counts", "lines", _ref_level_counts,
             """
             def level_counts(lines):
                 from collections import Counter
                 levels = []
                 for line in lines:
                     fields = line.split()
                     if len(fields) >= 3:
                         levels.append(fields[2])
                 return dict(Counter(levels))
             """,
             [("app log", [APP_LOG]), ("one line", [[APP_LOG[1]]])],
             [("ragged line ignored", [APP_LOG + ["", "  ", "2026-03-10 09:17:00"]]),
              ("all one level", [[APP_LOG[0], APP_LOG[4]]])],
             edges=[("no lines", [[]]), ("only junk", [["", "x", "x y"]])],
             difficulty="TUTORIAL", pattern="HASH_MAP", family="log_parsing",
             realm="stringwood_labyrinth",
             nudge="Collect the levels first, count them second. Two small steps beat "
                   "one clever one.",
             pseudocode="for line: fields = line.split(); if len >= 3: record fields[2]",
             failures=["Crashing on a blank line at the end of the file",
                       "Counting with a plain dict and no `.get(key, 0)` default"],
             tags=["logs"]),

        work("pt-log-worst-path", "The Endpoint That Is Bleeding",
             "Each line is `date time level service method path status ms`. Return "
             "the path with the most responses of status 500 or above. Break a tie "
             "by taking the lexicographically smallest path. Return \"\" when "
             "nothing failed. Lines that are too short, or whose status is not an "
             "integer, are skipped.",
             "worst_path", "lines", _ref_worst_path,
             """
             def worst_path(lines):
                 from collections import Counter
                 failures = Counter()
                 for line in lines:
                     fields = line.split()
                     if len(fields) < 7:
                         continue
                     try:
                         status = int(fields[6])
                     except ValueError:
                         continue
                     if status >= 500:
                         failures[fields[5]] += 1
                 if not failures:
                     return ""
                 return sorted(failures, key=lambda path: (-failures[path], path))[0]
             """,
             [("app log", [APP_LOG]),
              ("tie broken by name", [APP_LOG + [
                  "2026-03-10 09:16:00 ERROR api GET /v1/alpha 500 10"]])],
             [("nothing failed", [[APP_LOG[0], APP_LOG[2]]]),
              ("status not a number", [APP_LOG + [
                  "2026-03-10 09:16:00 ERROR api GET /v1/zeta xxx 10"]]),
              ("499 is not a server error", [[
                  "2026-03-10 09:16:00 WARN api GET /v1/zeta 499 10"]])],
             edges=[("no lines", [[]]),
                    ("every line ragged", [["a b c", ""]])],
             difficulty="EASY", pattern="HASH_MAP", family="log_parsing",
             realm="stringwood_labyrinth", secondary=["SORTING", "STRING"],
             nudge="Count first. Only once the counts exist does the tie-break rule "
                   "have anything to break.",
             pseudocode="count 5xx by path; sort by (-count, path); take the first",
             failures=["`max()` on a Counter picks an arbitrary winner among ties",
                       "Treating 404 as a failure — the rule said 500 and above",
                       "Letting one unparsable status kill the whole run"],
             tags=["logs", "aggregation"]),

        work("pt-log-per-minute", "Errors, By The Minute",
             "Return the ERROR count per minute as a sorted list of "
             "`[minute, count]` pairs, where `minute` is the first 16 characters of "
             "the line — `\"2026-03-10 09:14\"`. Minutes with no errors do not "
             "appear at all. Lines with fewer than three fields are skipped.",
             "errors_per_minute", "lines", _ref_errors_per_minute,
             """
             def errors_per_minute(lines):
                 from collections import defaultdict
                 buckets = defaultdict(int)
                 for line in lines:
                     fields = line.split()
                     if len(fields) < 3 or fields[2] != "ERROR":
                         continue
                     buckets[line[:16]] += 1
                 return [[minute, buckets[minute]] for minute in sorted(buckets)]
             """,
             [("app log", [APP_LOG]),
              ("two in one minute", [APP_LOG + [
                  "2026-03-10 09:15:59 ERROR api POST /v1/login 500 1"]])],
             [("no errors", [[APP_LOG[0], APP_LOG[2]]]),
              ("decoy message", [DECOY_LOG]),
              ("unsorted input still sorts", [list(reversed(APP_LOG))])],
             edges=[("no lines", [[]]), ("ragged only", [["", "x y"]])],
             difficulty="MEDIUM", pattern="HASH_MAP", family="log_parsing",
             realm="stringwood_labyrinth", secondary=["SORTING", "STRING"],
             nudge="The bucket key is a truncated timestamp. No date library required.",
             pseudocode="key = line[:16] for ERROR lines; count per key; sorted(keys)",
             failures=["Emitting every minute in the range instead of only the ones seen",
                       "Returning tuples where the tests expect lists"],
             tags=["logs", "aggregation"]),

        work("pt-log-sessions", "Reconstructing the Watch",
             "Each line is `date time user action` where action is `login` or "
             "`logout`. Pair each logout with that user's most recent unmatched "
             "login and return `[user, seconds]` for every completed session, "
             "sorted by user then duration.\n\n"
             "A logout with no open login is ignored. A login never logged out is "
             "ignored. A line that is not four fields, or whose timestamp will not "
             "parse, is skipped — the file is written by a service that sometimes "
             "dies mid-line.",
             "sessions", "lines", _ref_sessions,
             """
             def sessions(lines):
                 from datetime import datetime

                 open_logins, finished = {}, []
                 for line in lines:
                     fields = line.split()
                     if len(fields) != 4:
                         continue
                     try:
                         moment = datetime.strptime(fields[0] + " " + fields[1],
                                                    "%Y-%m-%d %H:%M:%S")
                     except ValueError:
                         continue
                     user, action = fields[2], fields[3]
                     if action == "login":
                         open_logins[user] = moment
                     elif action == "logout" and user in open_logins:
                         started = open_logins.pop(user)
                         finished.append([user, int((moment - started).total_seconds())])
                 finished.sort(key=lambda row: (row[0], row[1]))
                 return finished
             """,
             [("two sessions", [SESSION_LOG]),
              ("logout with no login", [SESSION_LOG[2:]])],
             [("relogin overwrites", [[
                 "2026-03-10 09:00:00 alice login",
                 "2026-03-10 09:01:00 alice login",
                 "2026-03-10 09:02:00 alice logout"]]),
              ("two sessions one user", [SESSION_LOG + [
                  "2026-03-10 09:20:00 alice login",
                  "2026-03-10 09:20:30 alice logout"]]),
              ("torn line", [SESSION_LOG + ["2026-03-10 09:2"]]),
              ("impossible timestamp", [[
                  "2026-03-10 25:00:00 dan login",
                  "2026-03-10 09:00:00 dan login",
                  "2026-03-10 09:00:10 dan logout"]])],
             edges=[("no lines", [[]]),
                    ("never logs out", [["2026-03-10 09:00:00 eve login"]])],
             difficulty="HARD", pattern="SIMULATION", family="log_parsing",
             realm="stringwood_labyrinth", secondary=["HASH_MAP", "SORTING"],
             nudge="One dict of user -> open login time is the entire state. Everything "
                   "else is bookkeeping.",
             pseudocode=("for each parsable line:\n"
                         "  login  -> open[user] = time\n"
                         "  logout -> if user in open: emit and delete\n"
                         "sort by (user, seconds)"),
             failures=["Assuming the file is sorted and pairing line i with line i+1",
                       "Letting one unparsable timestamp abort the whole file",
                       "Leaving the login open after emitting, so the next logout "
                       "pairs with it too"],
             tags=["logs", "stateful"],
             source_type="GENERAL_INTERVIEW",
             provenance="Log reconstruction is a commonly reported shape for "
                        "practical exercises at infrastructure-heavy teams."),
    ]


# ---------------------------------------------------------------------------
# 2. CSV in, report out
# ---------------------------------------------------------------------------

SALES_CSV = [
    "region,product,units",
    "north,widget,12",
    "south,widget,7",
    "north,gadget,5",
    "east,widget,nine",          # the row that ends careers
    "south,gadget,3",
]

SALES_DICTS = [
    {"region": "north", "product": "widget", "units": "12"},
    {"region": "south", "product": "widget", "units": "7"},
    {"region": "north", "product": "gadget", "units": "5"},
    {"region": "east", "product": "widget", "units": "nine"},
    {"region": "south", "product": "gadget", "units": "3"},
]


def _split_csv(line):
    """A hand-rolled quote-aware splitter, written to disagree with `csv` if
    either of us is wrong."""
    if line == "":
        return []
    fields, field, quoted, i = [], [], False, 0
    while i < len(line):
        ch = line[i]
        if quoted:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    field.append('"')
                    i += 1
                else:
                    quoted = False
            else:
                field.append(ch)
        elif ch == '"' and not field:
            quoted = True
        elif ch == ",":
            fields.append("".join(field))
            field = []
        else:
            field.append(ch)
        i += 1
    fields.append("".join(field))
    return fields


def _ref_split_row(line):
    return [part.strip() for part in line.split(",")]


def _ref_to_dicts(rows):
    if not rows:
        return []
    header = [name.strip() for name in rows[0].split(",")]
    out = []
    for line in rows[1:]:
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(header):
            continue
        out.append({header[i]: values[i] for i in range(len(header))})
    return out


def _ref_parse_quoted(line):
    return _split_csv(line)


def _ref_sum_by(records, group_by, amount):
    totals = {}
    for record in records:
        if group_by not in record or amount not in record:
            continue
        try:
            value = int(record[amount])
        except (TypeError, ValueError):
            continue
        totals[record[group_by]] = totals.get(record[group_by], 0) + value
    return totals


def _ref_sales_report(rows):
    records = _ref_to_dicts(rows)
    totals = _ref_sum_by(records, "region", "units")
    order = sorted(totals, key=lambda region: (-totals[region], region))
    out = ["%-12s%6d" % (region, totals[region]) for region in order]
    if rows:
        out.append("%-12s%6d" % ("TOTAL", sum(totals.values())))
    return out


def csvwork() -> list:
    return [
        guided(
            "pt-csv-split-row", "Cutting the Row",
            "Split one CSV line on commas and strip the whitespace off every "
            "field. No quoting in this file yet — that arrives two problems from "
            "now, and it is why the `csv` module exists.",
            "split_row", "line", _ref_split_row,
            """
            def split_row(line):
                return [field.strip() for field in line.split(",")]
            """,
            [('line.split(",")', "cut the line into fields on the separator")],
            [("plain", ["north,widget,12"]), ("padded", [" north , widget , 12 "])],
            [("one field", ["north"]), ("trailing comma", ["north,"]),
             ("empty middle", ["a,,b"])],
            edges=[("empty line", [""])],
            pattern="STRING", family="csv_report",
            scaffold_for="ONE ROW, CUT INTO FIELDS",
            failures=["`.split()` with no argument splits on whitespace, not commas"],
        ),

        work("pt-csv-to-dicts", "Naming the Columns",
             "`rows` is a CSV file as a list of lines. The first line is the "
             "header. Return one dict per data row, mapping column name to value, "
             "with whitespace stripped from both.\n\n"
             "A row whose field count does not match the header is skipped. It is "
             "not an exception — half the point of this exercise is that one bad "
             "row must not take down the run.",
             "to_dicts", "rows", _ref_to_dicts,
             """
             def to_dicts(rows):
                 if not rows:
                     return []
                 header = [name.strip() for name in rows[0].split(",")]
                 records = []
                 for line in rows[1:]:
                     values = [value.strip() for value in line.split(",")]
                     if len(values) != len(header):
                         continue
                     records.append(dict(zip(header, values)))
                 return records
             """,
             [("sales file", [SALES_CSV]), ("header only", [[SALES_CSV[0]]])],
             [("short row skipped", [[SALES_CSV[0], "north,widget"]]),
              ("long row skipped", [[SALES_CSV[0], "north,widget,1,extra"]]),
              ("padding stripped", [[SALES_CSV[0], " north , widget , 12 "]])],
             edges=[("no rows at all", [[]]),
                    ("blank data row", [[SALES_CSV[0], ""]])],
             difficulty="TUTORIAL", pattern="ARRAY", family="csv_report",
             secondary=["HASH_MAP", "STRING"],
             nudge="`zip(header, values)` pairs them up, and `dict()` takes it from "
                   "there.",
             pseudocode="header = rows[0] split; for each later row: skip if widths "
                        "differ, else dict(zip(header, values))",
             failures=["Including the header line as a record",
                       "`dict(zip(...))` silently truncates, which is exactly why "
                       "the length check has to come first"],
             tags=["csv"]),

        work("pt-csv-quoted", "The Field With A Comma In It",
             "Return the fields of one CSV line, honouring double quotes: a quoted "
             "field may contain commas, and a doubled quote inside a quoted field "
             "means one literal quote character.\n\n"
             "You can hand-roll this. You should not. The stdlib has a parser that "
             "has already met every file you are about to meet — find it, and note "
             "that it reads an iterable of lines, so a single line goes in as a "
             "one-item list.",
             "parse_line", "line", _ref_parse_quoted,
             """
             def parse_line(line):
                 import csv

                 for fields in csv.reader([line]):
                     return fields
                 return []
             """,
             [("plain", ["north,widget,12"]),
              ("comma inside quotes", ['north,"widget, large",12'])],
             [("doubled quote", ['a,"say ""hi""",c']),
              ("empty fields", [",,"]),
              ("quoted empty", ['a,"",c'])],
             edges=[("empty line", [""]), ("single field", ["solo"])],
             difficulty="EASY", pattern="STRING", family="csv_report",
             nudge="`csv.reader` consumes lines, not a string. Give it a list of one.",
             pseudocode="next(csv.reader([line]))  # with an empty-line guard",
             failures=["`line.split(',')` cuts straight through a quoted comma",
                       "Forgetting that an empty line yields no row at all"],
             tags=["csv", "stdlib"]),

        work("pt-csv-sum-by", "Totals By Region",
             "`records` are dicts from a parsed CSV. Sum the `amount` column, "
             "grouped by the `group_by` column, and return a dict of group to "
             "total.\n\n"
             "Values arrive as strings, because CSV has no types. A record missing "
             "either column, or whose amount will not convert to an integer, is "
             "skipped — real files contain the word \"nine\".",
             "sum_by", "records, group_by, amount", _ref_sum_by,
             """
             def sum_by(records, group_by, amount):
                 from collections import defaultdict

                 totals = defaultdict(int)
                 for record in records:
                     if group_by not in record or amount not in record:
                         continue
                     try:
                         value = int(record[amount])
                     except (TypeError, ValueError):
                         continue
                     totals[record[group_by]] += value
                 return dict(totals)
             """,
             [("sales", [SALES_DICTS, "region", "units"]),
              ("by product", [SALES_DICTS, "product", "units"])],
             [("column missing", [[{"region": "north"}], "region", "units"]),
              ("all unparsable", [[{"region": "n", "units": "x"}], "region", "units"]),
              ("negative units", [[{"region": "n", "units": "-4"}], "region", "units"])],
             edges=[("no records", [[], "region", "units"]),
                    ("unknown column", [SALES_DICTS, "colour", "units"])],
             difficulty="EASY", pattern="HASH_MAP", family="csv_report",
             nudge="`try: int(...) except ValueError: continue` is the whole "
                   "malformed-row policy, stated in three lines.",
             pseudocode="for record: skip if columns absent; int() or skip; add to "
                        "totals[group]",
             failures=["Summing the strings, which concatenates instead of adding",
                       "`except:` bare, which also swallows the KeyboardInterrupt "
                       "you will one day need"],
             tags=["csv", "aggregation"]),

        work("pt-csv-report", "The Report Nobody Reads",
             "Turn a CSV file into the report. `rows` is the file as a list of "
             "lines with a header. Total the `units` column per `region` and "
             "return one formatted line per region, then a TOTAL line.\n\n"
             "Each line is the region left-justified in 12 characters, then the "
             "total right-justified in 6 — `f\"{region:<12}{total:>6}\"`. Order by "
             "total descending, then by region ascending. Rows with the wrong "
             "field count, or an unparsable unit count, are dropped silently. An "
             "empty file produces no lines at all, TOTAL included.",
             "sales_report", "rows", _ref_sales_report,
             """
             def sales_report(rows):
                 if not rows:
                     return []
                 header = [name.strip() for name in rows[0].split(",")]
                 totals = {}
                 for line in rows[1:]:
                     values = [value.strip() for value in line.split(",")]
                     if len(values) != len(header):
                         continue
                     record = dict(zip(header, values))
                     try:
                         units = int(record["units"])
                     except (KeyError, ValueError):
                         continue
                     totals[record["region"]] = totals.get(record["region"], 0) + units

                 order = sorted(totals, key=lambda region: (-totals[region], region))
                 report = [f"{region:<12}{totals[region]:>6}" for region in order]
                 report.append(f"{'TOTAL':<12}{sum(totals.values()):>6}")
                 return report
             """,
             [("sales file", [SALES_CSV]), ("header only", [[SALES_CSV[0]]])],
             [("tie sorts by name", [[SALES_CSV[0], "south,a,4", "north,b,4"]]),
              ("every row bad", [[SALES_CSV[0], "north,widget", "east,widget,x"]]),
              ("one region", [[SALES_CSV[0], "north,widget,1", "north,gadget,2"]])],
             edges=[("empty file", [[]]),
                    ("no units column", [["region,product", "north,widget"]])],
             difficulty="MEDIUM", pattern="SORTING", family="csv_report",
             secondary=["HASH_MAP", "STRING"],
             time="O(n log n)",
             nudge="Parse, aggregate, order, format. Four separate steps; do not try "
                   "to do two of them in one comprehension.",
             pseudocode=("records = parse(rows)\n"
                         "totals  = sum units per region\n"
                         "order   = sorted by (-total, region)\n"
                         "lines   = f-string each, then append TOTAL"),
             failures=["Sorting by total alone, so ties come out in dict order",
                       "Emitting TOTAL for an empty file",
                       "Reversing a sort that already has a negative key"],
             tags=["csv", "report"],
             source_type="GENERAL_INTERVIEW",
             provenance="'Here is a CSV, produce this report' is among the most "
                        "commonly reported practical exercises."),
    ]


# ---------------------------------------------------------------------------
# 3. JSON that arrived in the wrong shape
# ---------------------------------------------------------------------------

API_PAYLOAD = {
    "teams": [
        {"name": "core", "members": [
            {"id": "u1", "role": "dev"},
            {"id": "u2", "role": "sre"},
        ]},
        {"name": "edge", "members": [
            {"id": "u3", "role": "dev"},
            {"id": "u1", "role": "dev"},
            {"id": "u4"},
        ]},
        {"name": "ghost"},
    ]
}

HOST_RECORD = {
    "host": "db-01",
    "net": {"ip": "10.0.0.7", "ports": [5432, 9100]},
    "meta": {"owner": {"team": "core", "pager": "sre"}, "tags": {}},
}


def _ref_get_path(data, path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _ref_index_by(records, key):
    index = {}
    for record in records:
        if isinstance(record, dict) and key in record:
            index[record[key]] = record
    return index


def _ref_flatten(data):
    out = {}
    stack = [("", data)]
    while stack:
        prefix, value = stack.pop()
        if isinstance(value, dict) and value:
            for name in value:
                stack.append((prefix + "." + name if prefix else name, value[name]))
        else:
            out[prefix] = value
    return out


def _ref_by_role(payload):
    found = {}
    for team in payload.get("teams", []):
        for member in team.get("members", []):
            if "id" not in member or "role" not in member:
                continue
            found.setdefault(member["role"], set()).add(member["id"])
        # teams with no members key contribute nothing, and that is not an error
    return {role: sorted(ids) for role, ids in found.items()}


def jsonwork() -> list:
    return [
        guided(
            "pt-json-get-path", "Down The Nest",
            "Follow `path` — a list of keys — down through nested dicts and return "
            "what you land on. Return `default` the moment the path leaves the "
            "map: a missing key, or a value that is not a dict when there is still "
            "path left to walk.\n\n"
            "This is the function you write in the first ten minutes of every job "
            "that consumes somebody else's JSON.",
            "get_path", "data, path, default=None", _ref_get_path,
            """
            def get_path(data, path, default=None):
                current = data
                for key in path:
                    if not isinstance(current, dict) or key not in current:
                        return default
                    current = current[key]
                return current
            """,
            [("current = current[key]",
              "step down to the value this key points at")],
            [("two deep", [HOST_RECORD, ["net", "ip"]]),
             ("three deep", [HOST_RECORD, ["meta", "owner", "team"]])],
            [("missing key", [HOST_RECORD, ["net", "mac"]]),
             ("through a non-dict", [HOST_RECORD, ["host", "length"]]),
             ("returns a list", [HOST_RECORD, ["net", "ports"]])],
            edges=[("empty path returns the whole thing", [HOST_RECORD, []]),
                   ("default is used", [HOST_RECORD, ["nope"], "unknown"])],
            pattern="HASH_MAP", family="json_reshape", realm="hashmap_highlands",
            scaffold_for="WALKING A PATH THROUGH NESTED JSON",
            failures=["`data[a][b]` raises KeyError on the first absent key",
                      "`.get(a, {}).get(b)` works until a level holds a string"],
        ),

        work("pt-json-index-by", "The Lookup You Will Need Twice",
             "Turn a list of records into a dict keyed by one field, so lookups "
             "stop being linear scans. Records that are not dicts, or that lack "
             "the key, are skipped. When two records share a key, the later one "
             "wins — state that in a comment, because the next reader will ask.",
             "index_by", "records, key", _ref_index_by,
             """
             def index_by(records, key):
                 index = {}
                 for record in records:
                     if not isinstance(record, dict) or key not in record:
                         continue
                     # last write wins: callers rely on this for override files
                     index[record[key]] = record
                 return index
             """,
             [("by id", [[{"id": "a", "n": 1}, {"id": "b", "n": 2}], "id"]),
              ("duplicate key", [[{"id": "a", "n": 1}, {"id": "a", "n": 9}], "id"])],
             [("missing key skipped", [[{"id": "a"}, {"n": 2}], "id"]),
              ("non-dict skipped", [[{"id": "a"}, "junk", 7], "id"]),
              ("integer key", [[{"id": 1, "n": 1}], "id"])],
             edges=[("no records", [[], "id"]),
                    ("key nobody has", [[{"id": "a"}], "uuid"])],
             difficulty="TUTORIAL", pattern="HASH_MAP", family="json_reshape",
             realm="hashmap_highlands",
             nudge="One pass, one dict. The whole win is that every later lookup is "
                   "then free.",
             pseudocode="for record: if it has the key, index[record[key]] = record",
             failures=["Building a list of pairs and searching it later",
                       "Assuming every record has the key"],
             tags=["json"]),

        work("pt-json-flatten", "Flattening The Nest",
             "Flatten nested dicts into a single dict whose keys are the path "
             "joined with dots: `{\"a\": {\"b\": 1}}` becomes `{\"a.b\": 1}`.\n\n"
             "Lists are leaves — do not descend into them. A dict with no keys is "
             "also a leaf, and survives as an empty dict. This is what you do "
             "before writing nested JSON into anything that only speaks flat, "
             "which is most things.",
             "flatten", "data", _ref_flatten,
             """
             def flatten(data):
                 out = {}

                 def walk(prefix, value):
                     if isinstance(value, dict) and value:
                         for name, child in value.items():
                             walk(prefix + "." + name if prefix else name, child)
                     else:
                         out[prefix] = value

                 walk("", data)
                 return out
             """,
             [("host record", [HOST_RECORD]),
              ("one level", [{"a": 1, "b": 2}])],
             [("list stays whole", [{"net": {"ports": [1, 2]}}]),
              ("empty dict is a leaf", [{"meta": {"tags": {}}}]),
              ("four deep", [{"a": {"b": {"c": {"d": 1}}}}])],
             edges=[("empty input", [{}]),
                    ("key already contains a dot", [{"a.b": {"c": 1}}])],
             difficulty="EASY", pattern="HASH_MAP", family="json_reshape",
             realm="hashmap_highlands", secondary=["RECURSION"],
             nudge="A recursive helper that carries the prefix down is shorter than "
                   "any loop you can write for this.",
             pseudocode="walk(prefix, value): dict and non-empty -> recurse per key; "
                        "else out[prefix] = value",
             failures=["Descending into lists and producing keys like `ports.0`, "
                       "which the spec did not ask for",
                       "Dropping empty dicts entirely and losing the key"],
             tags=["json"]),

        work("pt-json-by-role", "Inverting The Org Chart",
             "The API returns teams, each with members. You need the opposite "
             "shape: a dict from role to the sorted, de-duplicated ids of everyone "
             "holding it.\n\n"
             "A team with no `members` key contributes nothing. A member missing "
             "`id` or `role` is skipped. Somebody appearing on two teams appears "
             "once in the answer.",
             "by_role", "payload", _ref_by_role,
             """
             def by_role(payload):
                 from collections import defaultdict

                 found = defaultdict(set)
                 for team in payload.get("teams", []):
                     for member in team.get("members", []):
                         if "id" in member and "role" in member:
                             found[member["role"]].add(member["id"])
                 return {role: sorted(ids) for role, ids in found.items()}
             """,
             [("api payload", [API_PAYLOAD]),
              ("one team", [{"teams": [API_PAYLOAD["teams"][0]]}])],
             [("no teams key", [{}]),
              ("team with no members", [{"teams": [{"name": "ghost"}]}]),
              ("everyone the same role", [{"teams": [{"members": [
                  {"id": "z", "role": "dev"}, {"id": "a", "role": "dev"}]}]}])],
             edges=[("empty teams", [{"teams": []}]),
                    ("member with neither field", [{"teams": [{"members": [{}]}]}])],
             difficulty="MEDIUM", pattern="HASH_MAP", family="json_reshape",
             realm="hashmap_highlands", secondary=["SET", "SORTING"],
             nudge="A set per role removes the duplicate before you ever have to "
                   "think about it; sort on the way out.",
             pseudocode="for team in payload.get('teams', []):\n"
                        "  for member in team.get('members', []):\n"
                        "    if id and role: found[role].add(id)\n"
                        "return {role: sorted(ids)}",
             failures=["`payload['teams']` raising on a response that omitted it",
                       "Appending to a list and returning duplicates",
                       "Returning sets, which do not survive JSON"],
             tags=["json", "reshape"]),
    ]


# ---------------------------------------------------------------------------
# 4. Config that arrives in layers
# ---------------------------------------------------------------------------

BASE_CONFIG = {
    "service": "api",
    "timeout": 30,
    "log": {"level": "INFO", "sinks": ["stdout"]},
    "limits": {"rps": 100, "burst": 20},
}
SITE_CONFIG = {"timeout": 5, "log": {"level": "DEBUG"}}
USER_CONFIG = {"log": {"sinks": ["file"]}, "limits": {"burst": 50}}


def _ref_override(base, extra):
    merged = dict(base)
    for key in extra:
        merged[key] = extra[key]
    return merged


def _ref_apply_layers(layers):
    merged = {}
    for layer in layers:
        merged = _ref_override(merged, layer)
    return merged


def _ref_deep_merge(base, extra):
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _ref_deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _ref_resolve(layers):
    merged = {}
    for layer in layers:
        for key, value in layer.items():
            if value is None:
                merged.pop(key, None)
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _ref_resolve([merged[key], value])
            elif isinstance(value, dict):
                merged[key] = _ref_resolve([value])
            else:
                merged[key] = value
    return merged


def configwork() -> list:
    return [
        guided(
            "pt-config-override", "One Layer Over Another",
            "Return a new dict holding `base` with `extra` laid over it. Keys in "
            "`extra` win.\n\n"
            "It must be a NEW dict. The caller is going to hand you the same base "
            "config for every request, and if you mutate it the second request "
            "inherits the first one's overrides. That bug takes a day to find.",
            "override", "base, extra", _ref_override,
            """
            def override(base, extra):
                merged = dict(base)
                merged.update(extra)
                return merged
            """,
            [("merged.update(extra)", "lay the second dict over the copy")],
            [("simple", [{"a": 1, "b": 2}, {"b": 9}]),
             ("adds a key", [{"a": 1}, {"c": 3}])],
            [("extra wins", [{"a": 1}, {"a": 2}]),
             ("empty extra", [{"a": 1}, {}]),
             ("empty base", [{}, {"a": 1}])],
            edges=[("both empty", [{}, {}]),
                   ("value is None", [{"a": 1}, {"a": None}])],
            pattern="HASH_MAP", family="config_merge", realm="hashmap_highlands",
            scaffold_for="LAYERING TWO FLAT CONFIGS",
            failures=["`base.update(extra); return base` mutates the caller's dict",
                      "`{**base, **extra}` is the same thing and also correct"],
        ),

        work("pt-config-layers", "Defaults, Then Site, Then You",
             "Fold a list of config layers left to right, later layers winning, and "
             "return the result. Flat keys only for now. Mutate nothing you were "
             "given.",
             "apply_layers", "layers", _ref_apply_layers,
             """
             def apply_layers(layers):
                 merged = {}
                 for layer in layers:
                     merged = {**merged, **layer}
                 return merged
             """,
             [("three layers", [[{"a": 1, "b": 1}, {"b": 2}, {"c": 3}]]),
              ("one layer", [[{"a": 1}]])],
             [("later wins", [[{"a": 1}, {"a": 2}, {"a": 3}]]),
              ("empty layer in the middle", [[{"a": 1}, {}, {"b": 2}]]),
              ("all empty", [[{}, {}]])],
             edges=[("no layers", [[]]),
                    ("None is just a value here", [[{"a": 1}, {"a": None}]])],
             difficulty="TUTORIAL", pattern="HASH_MAP", family="config_merge",
             realm="hashmap_highlands",
             nudge="`{**merged, **layer}` builds a new dict each time, which is "
                   "exactly the guarantee the statement asks for.",
             pseudocode="merged = {}; for layer: merged = {**merged, **layer}",
             failures=["Folding right to left, so the defaults win",
                       "Starting from `layers[0]` and mutating it"],
             tags=["config"]),

        work("pt-config-deep-merge", "All The Way Down",
             "Merge `extra` into `base` recursively. Where both sides hold a dict "
             "for the same key, merge those dicts too. Anywhere else, `extra` "
             "wins outright — including when it replaces a dict with a scalar, or "
             "a list with a list. Lists are values, not containers to merge.\n\n"
             "Neither input may be modified.",
             "deep_merge", "base, extra", _ref_deep_merge,
             """
             def deep_merge(base, extra):
                 merged = dict(base)
                 for key, value in extra.items():
                     current = merged.get(key)
                     if isinstance(current, dict) and isinstance(value, dict):
                         merged[key] = deep_merge(current, value)
                     else:
                         merged[key] = value
                 return merged
             """,
             [("site over base", [BASE_CONFIG, SITE_CONFIG]),
              ("user over base", [BASE_CONFIG, USER_CONFIG])],
             [("list replaces list", [{"s": [1, 2]}, {"s": [3]}]),
              ("scalar replaces dict", [{"log": {"level": "INFO"}}, {"log": "off"}]),
              ("dict replaces scalar", [{"log": "off"}, {"log": {"level": "INFO"}}]),
              ("new nested branch", [BASE_CONFIG, {"tls": {"verify": True}}])],
             edges=[("empty extra", [BASE_CONFIG, {}]),
                    ("empty base", [{}, SITE_CONFIG])],
             difficulty="EASY", pattern="HASH_MAP", family="config_merge",
             realm="hashmap_highlands", secondary=["RECURSION"],
             nudge="One condition decides everything: are BOTH sides dicts at this "
                   "key? If not, the override simply wins.",
             pseudocode="copy base; for key, value in extra:\n"
                        "  both dicts -> recurse\n  else -> take value",
             failures=["`base.update(extra)` replaces the whole nested dict and "
                       "silently loses every sibling key",
                       "Recursing when only one side is a dict, and crashing",
                       "Copying shallowly and then mutating a shared nested dict"],
             tags=["config"]),

        work("pt-config-resolve", "The Policy Resolver",
             "Resolve an ordered list of config layers into one config.\n\n"
             "Rules, in the order they bite:\n"
             "- a value of `None` DELETES that key from the result so far;\n"
             "- two dicts at the same key merge recursively, under these same rules;\n"
             "- anything else replaces what was there, lists included;\n"
             "- a dict laid over a non-dict replaces it outright;\n"
             "- no input layer is modified, ever.\n\n"
             "This is a real config system's semantics, including the one most "
             "people forget: deleting a key that was never set is not an error.",
             "resolve", "layers", _ref_resolve,
             """
             def resolve(layers):
                 merged = {}
                 for layer in layers:
                     merged = _lay(merged, layer)
                 return merged


             def _lay(current, layer):
                 out = dict(current)
                 for key, value in layer.items():
                     if value is None:
                         out.pop(key, None)
                     elif isinstance(value, dict):
                         base = out.get(key)
                         out[key] = _lay(base if isinstance(base, dict) else {}, value)
                     else:
                         out[key] = value
                 return out
             """,
             [("three real layers", [[BASE_CONFIG, SITE_CONFIG, USER_CONFIG]]),
              ("delete a key", [[BASE_CONFIG, {"timeout": None}]])],
             [("delete a nested key", [[BASE_CONFIG, {"log": {"level": None}}]]),
              ("delete what was never there", [[{"a": 1}, {"b": None}]]),
              ("delete then set again", [[{"a": 1}, {"a": None}, {"a": 2}]]),
              ("dict over scalar", [[{"log": "off"}, {"log": {"level": "INFO"}}]]),
              ("None inside a nested dict of its own", [[{}, {"log": {"x": None}}]])],
             edges=[("no layers", [[]]),
                    ("every layer empty", [[{}, {}, {}]])],
             difficulty="MEDIUM", pattern="HASH_MAP", family="config_merge",
             realm="hashmap_highlands", secondary=["RECURSION"],
             nudge="Write the two-layer case as its own function, then fold the list "
                   "with it. Trying to do both at once is where this gets hard.",
             pseudocode=("resolve: fold layers with lay()\n"
                         "lay(current, layer): copy; per key —\n"
                         "  None  -> pop\n  dict  -> recurse into a dict or into {}\n"
                         "  else  -> assign"),
             failures=["Treating `None` as a value to store rather than a delete",
                       "Recursing into the existing value when it is a string",
                       "`dict(current)` is shallow — recursing returns a fresh dict, "
                       "which is what keeps the inputs clean"],
             tags=["config", "semantics"]),
    ]


# ---------------------------------------------------------------------------
# 5. Regular expressions, including the one about not using them
# ---------------------------------------------------------------------------

ACCESS_OK = ('10.0.0.7 - - [10/Mar/2026:09:14:02 +0000] '
             '"GET /v1/session HTTP/1.1" 200 512')
ACCESS_OK2 = ('192.168.1.9 - - [10/Mar/2026:09:15:01 +0000] '
              '"POST /v1/login HTTP/1.1" 503 0')


def _ref_find_ipv4(text):
    return re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", text)


def _ref_parse_kv(text):
    pairs = {}
    for token in text.split():
        if "=" not in token:
            continue
        key, _, value = token.partition("=")
        if not key or not value:
            continue
        pairs[key] = value
    return pairs


def _ref_valid_tickets(ids):
    out = []
    for value in ids:
        if len(value) != 8:
            continue
        head, dash, tail = value[:3], value[3], value[4:]
        if head.isalpha() and head.isupper() and dash == "-" and tail.isdigit():
            out.append(value)
    return out


def _ref_parse_access(line):
    try:
        ip, rest = line.split(" - - ", 1)
        stamp, rest = rest.split("] ", 1)
    except ValueError:
        return {}
    if not ip or " " in ip or not stamp.startswith("["):
        return {}
    stamp = stamp[1:]
    if "[" in stamp or "]" in stamp or not stamp:
        return {}
    if not rest.startswith('"'):
        return {}
    request, _, tail = rest[1:].partition('" ')
    if not tail:
        return {}
    parts = request.split(" ")
    if len(parts) != 3:
        return {}
    method, path, proto = parts
    if not (method.isalpha() and method.isupper()) or not path or not proto:
        return {}
    numbers = tail.split(" ")
    if len(numbers) != 2 or not all(n.isdigit() for n in numbers):
        return {}
    return {"ip": ip, "time": stamp, "method": method, "path": path,
            "status": int(numbers[0]), "bytes": int(numbers[1])}


def regexwork() -> list:
    return [
        guided(
            "pt-regex-find-ipv4", "Four Runs Of Digits",
            "Return every IPv4-looking address in `text`, in order.\n\n"
            "This is a FINDER, not a validator: four runs of one to three digits "
            "separated by dots. It will happily find 999.999.999.999, and that is "
            "the correct behaviour for pulling candidates out of a log before you "
            "check them properly.",
            "find_ipv4", "text", _ref_find_ipv4,
            """
            def find_ipv4(text):
                import re

                pattern = r"\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}"
                return re.findall(pattern, text)
            """,
            [('r"\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}"',
              "four runs of one to three digits, dot-separated — and a bare `.` "
              "means any character, so the dots need escaping")],
            [("two addresses", ["denied 10.0.0.7 -> 192.168.1.254"]),
             ("none", ["no addresses in this line at all"])],
            [("a version number is only three parts", ["release 1.2.3 shipped"]),
             ("start of line", ["10.0.0.1 is the gateway"]),
             ("five parts finds the first four", ["odd 1.2.3.4.5 value"])],
            edges=[("empty text", [""]), ("just dots", ["...."])],
            pattern="STRING", family="regex", realm="stringwood_labyrinth",
            scaffold_for="A REGEX THAT FINDS, RATHER THAN VALIDATES",
            failures=["An unescaped `.` matches any character, so `1x2x3x4` matches",
                      "`\\d+` instead of `\\d{1,3}` changes which candidates you get"],
            tags=["regex"]),

        work("pt-regex-parse-kv", "key=value, Everywhere, Forever",
             "Half the log lines ever written are `key=value` pairs separated by "
             "spaces. Return them as a dict.\n\n"
             "A pair needs a non-empty name made of word characters and a non-empty "
             "value that runs to the next space. A token with no `=` is not a pair. "
             "When a name repeats, the last one wins.",
             "parse_kv", "text", _ref_parse_kv,
             """
             def parse_kv(text):
                 import re

                 return dict(re.findall(r"(\\w+)=(\\S+)", text))
             """,
             [("three pairs", ["user=alice action=login ip=10.0.0.7"]),
              ("bare words ignored", ["request failed user=bob"])],
             [("last one wins", ["a=1 a=2"]),
              ("no value", ["a= b=2"]),
              ("value contains an equals", ["q=a==b"]),
              ("value runs to the space", ["note=hello world"])],
             edges=[("empty text", [""]), ("just an equals sign", ["="])],
             difficulty="TUTORIAL", pattern="STRING", family="regex",
             realm="stringwood_labyrinth", secondary=["HASH_MAP"],
             nudge="Two capture groups in one `findall` give you pairs, and `dict()` "
                   "eats pairs.",
             pseudocode=r"dict(re.findall(r'(\w+)=(\S+)', text))",
             failures=["`.split('=')` on a value that itself contains an equals",
                       "`(\\w+)` on the value side, which stops at the first "
                       "punctuation and silently truncates"],
             tags=["regex"]),

        mcq_problem(
            id="pt-regex-wrong-tool", title="When The Regex Is The Wrong Tool",
            realm="stringwood_labyrinth", pattern="STRING", difficulty="TUTORIAL",
            family="regex", seconds=90,
            statement="You need the value of the `total` field from these API "
                      "responses. A colleague has opened with the regex below. "
                      "What is the strongest argument against shipping it?",
            code="""
            import re

            body = '{"order": {"id": 7, "total": 1250}, "note": "total: free"}'
            total = re.search(r'"total":\\s*(\\d+)', body).group(1)
            """,
            choices=[
                "It is slower than `json.loads`, and this endpoint is hot.",
                "The input is a structured format with a parser in the standard "
                "library. `json.loads(body)['order']['total']` reads the field the "
                "sender actually meant, survives reordering, nesting and escaping, "
                "and fails loudly instead of matching a `total` that happens to "
                "appear in free text.",
                "`\\d+` should be `[0-9]+`, because `\\d` also matches non-ASCII "
                "digits.",
                "`re.search` returns None on no match, so it needs a try/except and "
                "is otherwise fine.",
            ],
            answer=1,
            explanation="""
            Regex is for text with no grammar. JSON, XML, HTML, CSV and URLs all
            have a grammar and a parser that implements it, and the parser knows
            things your pattern does not: escaping, nesting, ordering, encoding.

            The failure here is not theoretical. Add a field before `total`, nest
            the object one level deeper, or put the word "total" inside a string —
            all three are legal JSON that the sender may produce tomorrow — and the
            regex either picks the wrong number or crashes on `None.group`.

            The honest rule: if the format has a parser, use the parser. Reach for a
            regex when the input is genuinely unstructured text, like a log line
            somebody's printf wrote.
            """,
            distractor_notes={
                "0": "Speed is not the argument; correctness is. The regex is "
                     "probably faster and still wrong.",
                "2": "True of `\\d` in Python, and irrelevant here — swapping it "
                     "does not make the approach correct.",
                "3": "Handling None hides the crash. It does not stop the pattern "
                     "matching the wrong `total`.",
            },
        ),

        work("pt-regex-tickets", "The Ticket Ids That Are Real",
             "Return the values of `ids` that are valid ticket references, in "
             "order. A valid reference is exactly three uppercase ASCII letters, a "
             "hyphen, then exactly four digits: `ABC-1234`.\n\n"
             "Nothing more and nothing less — `re.search` would accept "
             "`xxABC-1234yy`, which is how bad ids get into a database.",
             "valid_tickets", "ids", _ref_valid_tickets,
             """
             def valid_tickets(ids):
                 import re

                 pattern = re.compile(r"[A-Z]{3}-\\d{4}")
                 return [value for value in ids if pattern.fullmatch(value)]
             """,
             [("mixed bag", [["ABC-1234", "abc-1234", "AB-1234", "ZZZ-0000"]]),
              ("all good", [["AAA-0001", "QRS-9999"]])],
             [("too many digits", [["ABC-12345"]]),
              ("too few digits", [["ABC-123"]]),
              ("embedded in junk", [["xxABC-1234yy"]]),
              ("wrong separator", [["ABC_1234", "ABC 1234"]])],
             edges=[("empty list", [[]]), ("empty string", [[""]])],
             difficulty="EASY", pattern="STRING", family="regex",
             realm="stringwood_labyrinth",
             nudge="`fullmatch` anchors both ends for you. `match` only anchors the "
                   "start, and `search` anchors neither.",
             pseudocode=r"keep value if re.fullmatch(r'[A-Z]{3}-\d{4}', value)",
             failures=["`re.match` accepts `ABC-1234-extra`",
                       "`^...$` with `$` also matching before a trailing newline, "
                       "so `'ABC-1234\\n'` sneaks through"],
             tags=["regex", "validation"]),

        work("pt-regex-access-line", "One Line Of The Access Log",
             "Parse one line of a combined-style access log into a dict:\n\n"
             "`IP - - [TIME] \"METHOD PATH PROTO\" STATUS BYTES`\n\n"
             "Return `{ip, time, method, path, status, bytes}` with `status` and "
             "`bytes` as integers and `time` as the text between the brackets. A "
             "line that does not match the format exactly returns `{}` — the log "
             "has rotated mid-write before and it will again.\n\n"
             "METHOD is uppercase letters, PATH and PROTO contain no spaces, and "
             "STATUS and BYTES are digits. Named groups will keep this readable; "
             "six positional groups will not.",
             "parse_access", "line", _ref_parse_access,
             """
             def parse_access(line):
                 import re

                 pattern = re.compile(
                     r'(?P<ip>\\S+) - - \\[(?P<time>[^\\]]+)\\] '
                     r'"(?P<method>[A-Z]+) (?P<path>\\S+) (?P<proto>\\S+)" '
                     r'(?P<status>\\d+) (?P<bytes>\\d+)'
                 )
                 found = pattern.fullmatch(line)
                 if found is None:
                     return {}
                 fields = found.groupdict()
                 return {
                     "ip": fields["ip"],
                     "time": fields["time"],
                     "method": fields["method"],
                     "path": fields["path"],
                     "status": int(fields["status"]),
                     "bytes": int(fields["bytes"]),
                 }
             """,
             [("a good line", [ACCESS_OK]), ("a failing request", [ACCESS_OK2])],
             [("lowercase method", [ACCESS_OK.replace('"GET', '"get')]),
              ("status is not a number", [ACCESS_OK.replace(" 200 ", " abc ")]),
              ("bytes missing", [ACCESS_OK.rsplit(" ", 1)[0]]),
              ("space in the path", [ACCESS_OK.replace("/v1/session", "/v1/ session")])],
             edges=[("empty line", [""]), ("not a log line at all", ["garbage"])],
             difficulty="MEDIUM", pattern="STRING", family="regex",
             realm="stringwood_labyrinth", secondary=["HASH_MAP"],
             nudge="Build the pattern in pieces, as adjacent string literals, one "
                   "field per line. A single 200-character regex is unreviewable.",
             pseudocode=("compile a fullmatch pattern with named groups\n"
                         "no match -> {}\n"
                         "match -> groupdict, with status and bytes cast to int"),
             failures=["`search` instead of `fullmatch`, so trailing junk is accepted",
                       "`.*` for the timestamp, which is greedy and swallows the "
                       "closing bracket — `[^\\]]+` says what you mean",
                       "Returning the status as a string, so `>= 500` compares text"],
             tags=["regex", "logs"],
             source_type="GENERAL_INTERVIEW",
             provenance="Parsing a web-server access line is a recurring practical "
                        "exercise for infrastructure and security roles."),
    ]


# ---------------------------------------------------------------------------
# 6. Text: normalising, tokenising, templating, and the byte/character line
# ---------------------------------------------------------------------------

PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"


def _ref_normalise(text):
    return " ".join(text.split()).casefold()


def _ref_tokenise(text):
    out = []
    for word in text.split():
        cleaned = word.strip(PUNCTUATION).lower()
        if cleaned:
            out.append(cleaned)
    return out


def _ref_slugify(text):
    out, pending = [], False
    for ch in text.lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            if pending and out:
                out.append("-")
            out.append(ch)
            pending = False
        else:
            pending = True
    return "".join(out)


def _ref_truncate_bytes(text, limit):
    out, used = [], 0
    for ch in text:
        size = len(ch.encode("utf-8"))
        if used + size > limit:
            break
        out.append(ch)
        used += size
    return "".join(out)


def _ref_render(template, values):
    def replace(found):
        token = found.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        key = found.group(1)
        return str(values[key]) if key in values else token

    return re.sub(r"\{\{|\}\}|\{(\w+)\}", replace, template)


def textwork() -> list:
    return [
        guided(
            "pt-text-normalise", "One Space, One Case",
            "Normalise `text` for comparison: collapse every run of whitespace — "
            "spaces, tabs, newlines — to a single space, strip the ends, and "
            "case-fold it.\n\n"
            "`casefold()` rather than `lower()`: it is the one built for comparing, "
            "and it knows that the German ß folds to `ss`.",
            "normalise", "text", _ref_normalise,
            """
            def normalise(text):
                return " ".join(text.split()).casefold()
            """,
            [('" ".join(text.split())',
              "split on any whitespace, then rejoin with exactly one space")],
            [("ragged spacing", ["  Hello   World  "]),
             ("tabs and newlines", ["a\tb\nc"])],
            [("already clean", ["already clean"]),
             ("mixed case", ["MiXeD CaSe"]),
             ("only whitespace", ["   \t  "])],
            edges=[("empty", [""]), ("one word", ["Word"])],
            pattern="STRING", family="text_normalise", realm="stringwood_labyrinth",
            scaffold_for="NORMALISING TEXT BEFORE COMPARING IT",
            failures=["`text.replace('  ', ' ')` needs to be run repeatedly and "
                      "still misses tabs",
                      "`.split(' ')` with an argument keeps the empty strings"]),

        work("pt-text-tokenise", "Words, More Or Less",
             "Split `text` into lowercase words. Split on whitespace, then strip "
             "punctuation off each end of every word, and drop anything that is "
             "empty afterwards.\n\n"
             "Punctuation INSIDE a word stays: `don't` is one token and so is "
             "`10.0.0.7`. That is a decision, not an accident — write it down "
             "before you code it, because the next person will assume the other "
             "one.",
             "tokenise", "text", _ref_tokenise,
             """
             def tokenise(text):
                 import string

                 words = []
                 for word in text.split():
                     cleaned = word.strip(string.punctuation).lower()
                     if cleaned:
                         words.append(cleaned)
                 return words
             """,
             [("a sentence", ["The gate, it seems, is Shut."]),
              ("inner punctuation kept", ["don't ping 10.0.0.7."])],
             [("only punctuation", ["--- !!! ---"]),
              ("quoted word", ['he said "stop" twice']),
              ("hyphenated", ["well-known -leading trailing-"])],
             edges=[("empty", [""]), ("whitespace only", ["   "])],
             difficulty="TUTORIAL", pattern="STRING", family="text_normalise",
             realm="stringwood_labyrinth",
             nudge="`str.strip` takes a SET of characters to remove from both ends, "
                   "not a prefix. `string.punctuation` is that set already.",
             pseudocode="for word in text.split(): strip punctuation, lower, keep if "
                        "non-empty",
             failures=["`strip('.,!')` looks like it removes a suffix; it removes any "
                       "of those characters from both ends, repeatedly",
                       "Forgetting that stripping can leave an empty string"],
             tags=["text"]),

        work("pt-text-slugify", "A Name A URL Can Hold",
             "Turn `text` into a slug: lowercase, every run of characters that is "
             "not an ASCII letter or digit becomes a single hyphen, and there are "
             "no hyphens at either end.\n\n"
             "`Weekly Report: March 2026` becomes `weekly-report-march-2026`. "
             "Accented letters are not ASCII, so they are separators here — which "
             "means `Café Menu` slugs to `caf-menu`, and you should know that "
             "before a customer tells you.",
             "slugify", "text", _ref_slugify,
             """
             def slugify(text):
                 import re

                 return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
             """,
             [("a title", ["Weekly Report: March 2026"]),
              ("accents are separators", ["Café Menu"])],
             [("already a slug", ["already-a-slug"]),
              ("runs collapse", ["a   ---   b"]),
              ("leading and trailing junk", ["  !hello!  "])],
             edges=[("empty", [""]), ("no usable characters", ["!!!"])],
             difficulty="EASY", pattern="STRING", family="text_normalise",
             realm="stringwood_labyrinth", secondary=["ARRAY"],
             nudge="One substitution over a RUN of bad characters, then strip the "
                   "hyphens off the ends. Two steps, one line each.",
             pseudocode=r're.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")',
             failures=["Replacing each bad character individually, so `a - b` becomes "
                       "`a---b`",
                       "Stripping before substituting, which leaves a leading hyphen",
                       "`\\w` includes the underscore and every Unicode letter, "
                       "which is not what a URL slug means"],
             tags=["text"]),

        work("pt-text-truncate-bytes", "Where The Column Ends",
             "The column is `limit` BYTES wide, not characters. Return the longest "
             "prefix of `text` that fits in `limit` bytes when encoded as UTF-8, "
             "without cutting a character in half.\n\n"
             "One character is one to four bytes. `len(text)` counts characters and "
             "`len(text.encode())` counts bytes, and the day those two numbers "
             "disagree is the day the database rejects the row. `limit` is zero or "
             "more.",
             "truncate_bytes", "text, limit", _ref_truncate_bytes,
             """
             def truncate_bytes(text, limit):
                 # Slicing bytes can land mid-character; "ignore" drops exactly the
                 # incomplete tail that leaves behind, which is the whole trick.
                 return text.encode("utf-8")[:limit].decode("utf-8", "ignore")
             """,
             [("fits", ["hello", 10]), ("cuts an accented letter", ["café", 4])],
             [("exact fit", ["café", 5]),
              ("ascii cut", ["hello world", 5]),
              ("multi-byte first", ["日本語", 4]),
              ("four-byte character", ["a\U0001F600b", 3])],
             edges=[("limit zero", ["hello", 0]), ("empty text", ["", 5])],
             difficulty="EASY", pattern="STRING", family="text_normalise",
             realm="stringwood_labyrinth",
             time="O(n)", space="O(n)",
             nudge="Encode, slice the bytes, decode with an error policy that drops "
                   "the incomplete tail.",
             pseudocode='text.encode("utf-8")[:limit].decode("utf-8", "ignore")',
             failures=["`text[:limit]` truncates characters, not bytes, and overflows "
                       "the column anyway",
                       "`decode()` with the default strict policy raises "
                       "UnicodeDecodeError on the half character",
                       "Assuming one character is one byte, which is true right up "
                       "until a user types their own name"],
             tags=["text", "encoding"]),

        work("pt-text-render", "The Template Nobody Escaped",
             "Render a template. `{name}` is replaced by `str(values['name'])`. "
             "`{{` and `}}` are literal braces. A placeholder whose name is not in "
             "`values` is left exactly as it was written — this renders "
             "half-finished emails, and silently producing `None` there is worse "
             "than leaving the marker visible.\n\n"
             "A placeholder name is one or more word characters. Anything else "
             "between braces — a space, an empty pair, an unclosed brace — is "
             "ordinary text.\n\n"
             "`str.format` cannot do this: it raises on the first unknown key, and "
             "it will happily evaluate `{a.__class__}` on whatever you hand it.",
             "render", "template, values", _ref_render,
             """
             def render(template, values):
                 out, i, n = [], 0, len(template)
                 while i < n:
                     ch = template[i]
                     if ch == "{" and template[i + 1:i + 2] == "{":
                         out.append("{")
                         i += 2
                         continue
                     if ch == "}" and template[i + 1:i + 2] == "}":
                         out.append("}")
                         i += 2
                         continue
                     if ch == "{":
                         end = template.find("}", i + 1)
                         key = template[i + 1:end] if end != -1 else ""
                         known = key and all(c.isalnum() or c == "_" for c in key)
                         if end != -1 and known and key in values:
                             out.append(str(values[key]))
                             i = end + 1
                             continue
                     out.append(ch)
                     i += 1
                 return "".join(out)
             """,
             [("two fields", ["Hello {name}, you have {count} messages",
                              {"name": "Ada", "count": 3}]),
              ("unknown stays", ["Dear {title} {surname}", {"surname": "Vail"}])],
             [("escaped braces", ["{{name}} is literal", {"name": "Ada"}]),
              ("value straight after a placeholder", ["{a}}", {"a": "X"}]),
              ("space inside braces is not a placeholder", ["{a b}", {"a": "X"}]),
              ("empty braces", ["{}", {"": "X"}]),
              ("unclosed brace", ["a { b", {"b": "X"}]),
              ("non-string value", ["n={n}", {"n": [1, 2]}])],
             edges=[("empty template", ["", {"a": 1}]),
                    ("no values at all", ["{a} {b}", {}])],
             difficulty="MEDIUM", pattern="STRING", family="text_normalise",
             realm="stringwood_labyrinth", secondary=["SIMULATION"],
             nudge="Walk the string with an index. Every branch either appends and "
                   "advances one, or appends and jumps past what it consumed.",
             pseudocode=("while i < len:\n"
                         "  '{{' or '}}' -> literal brace, i += 2\n"
                         "  '{' with a known word key and a closing brace -> value\n"
                         "  otherwise -> copy one character"),
             failures=["`str.format(**values)` raises KeyError on the first unknown "
                       "placeholder and cannot be made not to",
                       "`.replace('{'+k+'}', v)` rewrites text that a previous "
                       "substitution just inserted",
                       "Consuming the closing brace twice, so the next character is "
                       "eaten"],
             tags=["text", "templating"]),
    ]


# ---------------------------------------------------------------------------
# 7. Time: parsing it, subtracting it, sorting by it, bucketing it
# ---------------------------------------------------------------------------

ACCESS_TIMES = [
    {"id": "a", "at": "10/Mar/2026:09:14:02"},
    {"id": "b", "at": "09/Mar/2026:23:59:59"},
    {"id": "c", "at": "10/Mar/2026:09:14:01"},
    {"id": "d", "at": "01/Dec/2025:00:00:00"},
]

OFFSET_STAMPS = [
    "2026-03-10T09:14:02+00:00",
    "2026-03-10T11:44:00+02:00",      # 09:44 UTC, same hour bucket as the first
    "2026-03-10T10:00:00+00:00",
    "2026-03-10T09:59:59+00:00",
]


def _ref_stamp_fields(text):
    date_part, time_part = text.split(" ")
    year, month, day = (int(v) for v in date_part.split("-"))
    hour, minute, second = (int(v) for v in time_part.split(":"))
    return [year, month, day, hour, minute, second]


def _ref_elapsed(start, end):
    fmt = "%Y-%m-%d %H:%M:%S"
    delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
    return int(delta.total_seconds())


def _ref_by_time(records):
    def moment(record):
        return datetime.strptime(record["at"], "%d/%b/%Y:%H:%M:%S")

    return [record["id"] for record in sorted(records, key=moment)]


def _ref_duration(seconds):
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return "%dd %02d:%02d:%02d" % (days, hours, minutes, secs)
    return "%02d:%02d:%02d" % (hours, minutes, secs)


def _ref_utc_hours(stamps):
    counts = {}
    for stamp in stamps:
        try:
            moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            continue
        moment = moment.astimezone(timezone.utc)
        key = moment.strftime("%Y-%m-%dT%H")
        counts[key] = counts.get(key, 0) + 1
    return [[key, counts[key]] for key in sorted(counts)]


def timework() -> list:
    return [
        guided(
            "pt-time-fields", "Reading The Clock",
            "Parse `\"2026-03-10 09:14:02\"` and return "
            "`[year, month, day, hour, minute, second]` as integers.\n\n"
            "The format string is the whole problem. `%Y` is a four-digit year and "
            "`%y` is two; `%M` is minutes and `%m` is months; the literal spaces, "
            "dashes and colons in the format have to line up with the ones in the "
            "text, character for character.",
            "stamp_fields", "text", _ref_stamp_fields,
            """
            def stamp_fields(text):
                from datetime import datetime

                moment = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
                return [moment.year, moment.month, moment.day,
                        moment.hour, moment.minute, moment.second]
            """,
            [('"%Y-%m-%d %H:%M:%S"',
              "a four-digit year, month and day, then 24-hour time — matching the "
              "punctuation exactly")],
            [("an ordinary stamp", ["2026-03-10 09:14:02"]),
             ("midnight", ["2026-01-01 00:00:00"])],
            [("end of a year", ["2025-12-31 23:59:59"]),
             ("leap day", ["2024-02-29 12:00:00"]),
             ("single-digit fields are still padded", ["2026-03-01 01:02:03"])],
            edges=[("first second of the century", ["2000-01-01 00:00:00"])],
            pattern="STRING", family="datetime_work",
            scaffold_for="strptime AND ITS FORMAT STRING",
            failures=["`%M` where you meant `%m` parses minutes into the month",
                      "`%H` is 24-hour; `%I` is 12-hour and needs `%p` beside it"]),

        work("pt-time-elapsed", "How Long Was That",
             "Return the whole number of seconds from `start` to `end`. Both are "
             "`\"YYYY-MM-DD HH:MM:SS\"`. The answer is negative when `end` is "
             "earlier — do not take the absolute value, because the caller is "
             "checking for clock skew.",
             "elapsed_seconds", "start, end", _ref_elapsed,
             """
             def elapsed_seconds(start, end):
                 from datetime import datetime

                 fmt = "%Y-%m-%d %H:%M:%S"
                 delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
                 return int(delta.total_seconds())
             """,
             [("a minute", ["2026-03-10 09:14:02", "2026-03-10 09:15:02"]),
              ("backwards", ["2026-03-10 09:15:02", "2026-03-10 09:14:02"])],
             [("across midnight", ["2026-03-10 23:59:59", "2026-03-11 00:00:01"]),
              ("across a year", ["2025-12-31 23:59:59", "2026-01-01 00:00:00"]),
              ("across a leap day", ["2024-02-28 12:00:00", "2024-03-01 12:00:00"])],
             edges=[("same instant", ["2026-03-10 09:14:02", "2026-03-10 09:14:02"])],
             difficulty="TUTORIAL", pattern="STRING", family="datetime_work",
             nudge="Subtracting two datetimes gives a timedelta. It already knows "
                   "about months, years and leap days.",
             pseudocode="int((strptime(end) - strptime(start)).total_seconds())",
             failures=["`delta.seconds` is the seconds WITHIN the day and is never "
                       "negative — `total_seconds()` is the one you want",
                       "Subtracting the string fields by hand and rediscovering "
                       "February"],
             tags=["datetime"]),

        work("pt-time-sort", "Sorted By When, Not By Spelling",
             "Return the `id` of every record, ordered by its `at` timestamp, "
             "earliest first. Timestamps are in access-log format: "
             "`10/Mar/2026:09:14:02`.\n\n"
             "Sorting these as strings puts December before March and 2025 after "
             "2026. Parse first, then sort on the parsed value.",
             "by_time", "records", _ref_by_time,
             """
             def by_time(records):
                 from datetime import datetime

                 def moment(record):
                     return datetime.strptime(record["at"], "%d/%b/%Y:%H:%M:%S")

                 return [record["id"] for record in sorted(records, key=moment)]
             """,
             [("four records", [ACCESS_TIMES]), ("already ordered", [ACCESS_TIMES[3:]])],
             [("one second apart", [[ACCESS_TIMES[0], ACCESS_TIMES[2]]]),
              ("identical stamps keep input order", [[
                  {"id": "x", "at": "10/Mar/2026:09:14:02"},
                  {"id": "y", "at": "10/Mar/2026:09:14:02"}]]),
              ("across the year boundary", [[ACCESS_TIMES[3], ACCESS_TIMES[1]]])],
             edges=[("no records", [[]]), ("one record", [ACCESS_TIMES[:1]])],
             difficulty="EASY", pattern="SORTING", family="datetime_work",
             time="O(n log n)",
             nudge="`sorted(..., key=...)` where the key parses the timestamp. Python "
                   "sorts are stable, so equal times keep their order.",
             pseudocode='sorted(records, key=lambda r: strptime(r["at"], fmt))',
             failures=["Sorting on the raw string, which orders by month NAME",
                       "`%b` is the abbreviated month name — `%B` is the full one",
                       "Parsing inside a comparison function instead of a key, which "
                       "parses the same record over and over"],
             tags=["datetime", "sorting"]),

        work("pt-time-duration", "Saying How Long",
             "Format a whole number of seconds for a human: `\"HH:MM:SS\"`, with "
             "hours, minutes and seconds zero-padded to two digits. Once it passes "
             "a day, prefix it: `\"2d 03:04:05\"`. Hours do not roll over into "
             "days unless there is at least one whole day.\n\n"
             "`seconds` is zero or more.",
             "format_duration", "seconds", _ref_duration,
             """
             def format_duration(seconds):
                 seconds = int(seconds)
                 days = seconds // 86400
                 hours = seconds % 86400 // 3600
                 minutes = seconds % 3600 // 60
                 secs = seconds % 60
                 if days:
                     return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
                 return f"{hours:02d}:{minutes:02d}:{secs:02d}"
             """,
             [("an hour and a bit", [3725]), ("two days", [183845])],
             [("under a minute", [7]),
              ("exactly a day", [86400]),
              ("one second short of a day", [86399]),
              ("padding matters", [61])],
             edges=[("zero", [0]), ("a long outage", [1000000])],
             difficulty="EASY", pattern="STRING", family="datetime_work",
             time="O(1)", space="O(1)",
             nudge="`divmod` twice, or `//` and `%` four times. Either is fine; "
                   "mixing them halfway is not.",
             pseudocode="days, rest = divmod(seconds, 86400); then 3600; then 60",
             failures=["`str(timedelta(seconds=n))` produces `2 days, 3:04:05`, "
                       "which is a different format from the one specified",
                       "Zero-padding the days too, so `2d` becomes `02d`",
                       "Using `/` instead of `//` and formatting a float"],
             tags=["datetime"]),

        work("pt-time-utc-hours", "Everything In One Timezone",
             "Count events per UTC hour. Each stamp is ISO 8601 WITH an offset — "
             "`2026-03-10T11:44:00+02:00`. Convert each to UTC and bucket by "
             "`\"YYYY-MM-DDTHH\"`. Return the buckets that have events, sorted, as "
             "`[bucket, count]` pairs.\n\n"
             "A stamp with no offset is skipped. Not because it is hard — because "
             "it does not identify an instant, and guessing that it means the "
             "server's local time is how an incident timeline ends up an hour "
             "wrong. Anything else unparsable is skipped too.",
             "utc_hours", "stamps", _ref_utc_hours,
             """
             def utc_hours(stamps):
                 from collections import defaultdict
                 from datetime import datetime, timezone

                 counts = defaultdict(int)
                 for stamp in stamps:
                     try:
                         moment = datetime.fromisoformat(stamp)
                     except ValueError:
                         continue
                     if moment.tzinfo is None:
                         continue            # naive: not an instant, not our problem
                     counts[moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")] += 1
                 return [[key, counts[key]] for key in sorted(counts)]
             """,
             [("four stamps, three buckets", [OFFSET_STAMPS]),
              ("one stamp", [OFFSET_STAMPS[:1]])],
             [("naive stamp skipped", [OFFSET_STAMPS + ["2026-03-10T09:30:00"]]),
              ("nonsense skipped", [OFFSET_STAMPS + ["not a time"]]),
              ("offset crosses midnight", [["2026-03-10T00:30:00+02:00"]]),
              ("negative offset", [["2026-03-10T22:30:00-05:00"]])],
             edges=[("no stamps", [[]]), ("every stamp naive", [["2026-03-10T09:30:00"]])],
             difficulty="MEDIUM", pattern="HASH_MAP", family="datetime_work",
             secondary=["SORTING", "STRING"],
             time="O(n log n)",
             nudge="Convert to UTC first, then take the bucket key. Bucketing before "
                   "converting buckets the wrong hour.",
             pseudocode=("for stamp: fromisoformat -> skip naive and unparsable\n"
                         "key = astimezone(utc).strftime('%Y-%m-%dT%H')\n"
                         "count, then sort the keys"),
             failures=["Slicing the first 13 characters of the string, which buckets "
                       "local time and quietly mixes timezones",
                       "`astimezone()` on a naive datetime assumes the machine's "
                       "local timezone — a different answer on a different laptop",
                       "Emitting empty hours between the buckets that exist"],
             tags=["datetime", "timezones"]),
    ]


# ---------------------------------------------------------------------------
# 8. Files, read one line at a time, with a bad row in the middle
# ---------------------------------------------------------------------------
#
# Every function here takes an ITERABLE OF LINES rather than a path. That is not
# a testing dodge, it is the better signature: `with open(path) as fh:
# settings(fh)` works, and so does a list, a StringIO, or the output of another
# generator. A function that opens its own file can only ever be tested with a
# real file on a real disk.

SETTINGS_FILE = [
    "# gateway settings\n",
    "\n",
    "host = 10.0.0.7\n",
    "port = 8443\n",
    "   \n",
    "# port = 8080   (old, kept for the changelog)\n",
    "retries=3\n",
    "this line has no equals sign\n",
    "motd = welcome = to the gateway\n",
]

LEDGER_FILE = [
    "l-1|widgets|120\n",
    "\n",
    "l-2|gadgets|nine\n",
    "l-3|doohickeys\n",
    "l-4|sprockets|7\n",
]


def _ref_clean_lines(lines):
    return [line.strip() for line in lines if line.strip()]


def _ref_strip_comments(lines):
    out = []
    for line in lines:
        text = line.strip()
        if text and not text.startswith("#"):
            out.append(text)
    return out


def _ref_settings(lines):
    found = {}
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, value = text.partition("=")
        found[key.strip()] = value.strip()
    return found


def _ref_ledger(lines):
    good, bad = [], []
    for number, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text:
            continue
        parts = text.split("|")
        if len(parts) != 3:
            bad.append(number)
            continue
        try:
            amount = int(parts[2])
        except ValueError:
            bad.append(number)
            continue
        good.append({"id": parts[0].strip(), "item": parts[1].strip(),
                     "amount": amount})
    return [good, bad]


def filework() -> list:
    return [
        guided(
            "pt-file-clean", "Lines, Without The Newline",
            "`lines` is a file, one string per line, each still carrying its "
            "trailing newline. Return the lines with whitespace stripped from both "
            "ends, dropping the ones that are empty afterwards.\n\n"
            "Iterating a file gives you the `\\n`. Forgetting that is how "
            "`\"8443\\n\" == \"8443\"` becomes False at two in the morning.",
            "clean_lines", "lines", _ref_clean_lines,
            """
            def clean_lines(lines):
                return [line.strip() for line in lines if line.strip()]
            """,
            [("line.strip() for line in lines",
              "strip each line before anything else looks at it")],
            [("a settings file", [SETTINGS_FILE]),
             ("already clean", [["a", "b"]])],
            [("whitespace-only line dropped", [["  \n", "x\n"]]),
             ("no trailing newline on the last line", [["a\n", "b"]]),
             ("windows line ending", [["a\r\n"]])],
            edges=[("no lines", [[]]), ("every line blank", [["\n", "  \n"]])],
            pattern="STRING", family="file_lines", realm="python_village",
            scaffold_for="READING A FILE WITHOUT THE NEWLINES",
            failures=["`line[:-1]` eats a real character when the last line has no "
                      "newline, and leaves `\\r` on a Windows file",
                      "`.rstrip()` alone keeps the leading indentation"]),

        work("pt-file-comments", "Ignoring The Commentary",
             "Return the meaningful lines of a config file: stripped, with blank "
             "lines and whole-line comments removed. A comment is a line whose "
             "first non-whitespace character is `#`.\n\n"
             "Only whole-line comments. A `#` in the middle of a line stays, "
             "because it might be in a password.",
             "strip_comments", "lines", _ref_strip_comments,
             """
             def strip_comments(lines):
                 kept = []
                 for line in lines:
                     text = line.strip()
                     if not text or text.startswith("#"):
                         continue
                     kept.append(text)
                 return kept
             """,
             [("settings file", [SETTINGS_FILE]),
              ("no comments", [["a\n", "b\n"]])],
             [("indented comment", [["   # indented\n", "keep\n"]]),
              ("hash in the middle stays", [["pass = a#b\n"]]),
              ("comment with no space", [["#x\n"]])],
             edges=[("no lines", [[]]), ("all comments", [["# a\n", "# b\n"]])],
             difficulty="TUTORIAL", pattern="STRING", family="file_lines",
             realm="python_village",
             nudge="Strip once, into a variable, then ask both questions of that "
                   "variable.",
             pseudocode="for line: text = line.strip(); skip if empty or starts with #",
             failures=["`line.startswith('#')` before stripping misses the indented "
                       "comment",
                       "Splitting on `#` and truncating, which mangles a value that "
                       "legitimately contains one"],
             tags=["files"]),

        work("pt-file-settings", "The Settings File",
             "Parse `key = value` lines into a dict. Blank lines and whole-line "
             "comments are ignored. Whitespace around the key and the value is "
             "stripped. A line with no `=` at all is malformed and is skipped — "
             "silently, because one bad line must not stop the gateway from "
             "booting.\n\n"
             "Split on the FIRST `=` only: `motd = welcome = to the gateway` is a "
             "key and a value, not an error. Later definitions of a key replace "
             "earlier ones.",
             "settings", "lines", _ref_settings,
             """
             def settings(lines):
                 found = {}
                 for line in lines:
                     text = line.strip()
                     if not text or text.startswith("#") or "=" not in text:
                         continue
                     key, _, value = text.partition("=")
                     found[key.strip()] = value.strip()
                 return found
             """,
             [("settings file", [SETTINGS_FILE]),
              ("no spacing", [["retries=3\n"]])],
             [("second definition wins", [["a = 1\n", "a = 2\n"]]),
              ("value contains an equals", [["motd = a = b\n"]]),
              ("empty value", [["a =\n"]]),
              ("commented-out setting stays commented", [["# port = 8080\n"]])],
             edges=[("no lines", [[]]), ("nothing parsable", [["junk\n", "\n"]])],
             difficulty="EASY", pattern="HASH_MAP", family="file_lines",
             realm="python_village", secondary=["STRING"],
             nudge="`str.partition('=')` splits once and always returns three parts, "
                   "so there is no unpacking error to handle.",
             pseudocode="skip blank/comment/no-equals; key, _, value = "
                        "text.partition('='); store stripped",
             failures=["`key, value = text.split('=')` raises on a value containing "
                       "an equals sign",
                       "`split('=', 1)` is correct but still needs the `=` check "
                       "first, or it returns a one-element list"],
             tags=["files", "config"]),

        work("pt-file-ledger", "The Row That Is Wrong",
             "Parse a pipe-delimited ledger into `[records, bad_line_numbers]`.\n\n"
             "A good line is `id|item|amount` with an integer amount, and becomes "
             "`{\"id\": ..., \"item\": ..., \"amount\": <int>}`. A line with the "
             "wrong number of fields, or an amount that will not convert, "
             "contributes its 1-BASED line number to the second list instead. Blank "
             "lines are skipped and are not errors.\n\n"
             "The point is the shape of the return value: the run completes, AND "
             "the operator gets told which rows to go and look at. A parser that "
             "raises on line 3 of 40,000 has answered nobody's question.",
             "read_ledger", "lines", _ref_ledger,
             """
             def read_ledger(lines):
                 records, bad = [], []
                 for number, raw in enumerate(lines, 1):
                     record = _parse(raw)
                     if record is None and raw.strip():
                         bad.append(number)
                     elif record is not None:
                         records.append(record)
                 return [records, bad]


             def _parse(raw):
                 parts = raw.strip().split("|")
                 if len(parts) != 3:
                     return None
                 try:
                     amount = int(parts[2])
                 except ValueError:
                     return None
                 return {"id": parts[0].strip(), "item": parts[1].strip(),
                         "amount": amount}
             """,
             [("ledger with two bad rows", [LEDGER_FILE]),
              ("all good", [[LEDGER_FILE[0], LEDGER_FILE[4]]])],
             [("bad amount", [["l-1|widgets|nine\n"]]),
              ("too many fields", [["a|b|c|d\n"]]),
              ("blank lines do not shift the numbering", [["\n", "\n", "a|b|c\n"]]),
              ("negative amount is fine", [["l-9|returns|-4\n"]])],
             edges=[("empty file", [[]]), ("only blank lines", [["\n", "  \n"]])],
             difficulty="MEDIUM", pattern="ARRAY", family="file_lines",
             realm="python_village", secondary=["STRING", "SIMULATION"],
             nudge="`enumerate(lines, 1)` gives you the line number the operator will "
                   "actually see in their editor.",
             pseudocode=("for number, raw in enumerate(lines, 1):\n"
                         "  blank -> skip\n  parses -> append record\n"
                         "  otherwise -> append number to bad"),
             failures=["Counting only the non-blank lines, so every reported number "
                       "is wrong from the first blank onward",
                       "Raising on the first bad row and losing the other 39,999",
                       "`enumerate(lines)` starting at 0, which is off by one from "
                       "every text editor on earth"],
             tags=["files", "resilience"],
             source_type="GENERAL_INTERVIEW",
             provenance="Tolerating a malformed row while still reporting it is a "
                        "commonly reported follow-up in data-handling exercises."),
    ]


# ---------------------------------------------------------------------------
# 9. Add a feature to a module you did not write
# ---------------------------------------------------------------------------
#
# The reported practical exercise, stated plainly. The modules below are written
# the way real modules are written: a docstring that is slightly out of date, a
# helper nobody calls, a constant left over from a rewrite, names that were fine
# at the time. Reading past all that is the exercise, and it is why these are the
# most valuable problems in this file.

TALLY_BEFORE = '''
"""tally.py — event accounting for the quest log.

Counts events by kind. Written in a hurry before the Chapter VII demo and not
much touched since.
"""


def tally(events):
    """Count events by kind. Events with no kind are not counted."""
    counts = {}
    for event in events:
        kind = event.get("kind")
        if kind is None:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def total(events):
    """Total number of counted events. Unused since the dashboard rewrite."""
    return sum(tally(events).values())
'''

TALLY_AFTER = '''
"""tally.py — event accounting for the quest log.

Counts events by kind. Written in a hurry before the Chapter VII demo and not
much touched since.
"""


def tally(events, exclude=()):
    """Count events by kind. Events with no kind are not counted.

    Kinds named in `exclude` are left out of the result entirely.
    """
    skip = set(exclude)
    counts = {}
    for event in events:
        kind = event.get("kind")
        if kind is None or kind in skip:
            continue
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def total(events):
    """Total number of counted events. Unused since the dashboard rewrite."""
    return sum(tally(events).values())
'''

GATEWAY_BEFORE = '''
"""gateway_report.py — what the edge did today.

Reads records that access.py has already parsed. This module only counts, and
is kept deliberately boring.
"""

SERVER_ERROR = 500

# BUCKETS was read by the old dashboard. Nothing reads it now.
BUCKETS = ("ok", "server_errors")


def _status_of(record):
    """The status of a record, or None when it is missing or not an integer."""
    status = record.get("status")
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def summarise(records):
    """Count outcomes across a day of access records."""
    counted = 0
    ok = 0
    server_errors = 0
    slowest = 0
    for record in records:
        status = _status_of(record)
        if status is None:
            continue
        counted += 1
        if status < 400:
            ok += 1
        elif status >= SERVER_ERROR:
            server_errors += 1
        took = record.get("ms", 0)
        if isinstance(took, int) and took > slowest:
            slowest = took
    return {
        "total": counted,
        "ok": ok,
        "server_errors": server_errors,
        "slowest_ms": slowest,
    }
'''

GATEWAY_AFTER = '''
"""gateway_report.py — what the edge did today.

Reads records that access.py has already parsed. This module only counts, and
is kept deliberately boring.
"""

SERVER_ERROR = 500
CLIENT_ERROR = 400

# BUCKETS was read by the old dashboard. Nothing reads it now.
BUCKETS = ("ok", "server_errors")


def _status_of(record):
    """The status of a record, or None when it is missing or not an integer."""
    status = record.get("status")
    if isinstance(status, bool) or not isinstance(status, int):
        return None
    return status


def summarise(records):
    """Count outcomes across a day of access records."""
    counted = 0
    ok = 0
    client_errors = 0
    server_errors = 0
    slowest = 0
    for record in records:
        status = _status_of(record)
        if status is None:
            continue
        counted += 1
        if status < CLIENT_ERROR:
            ok += 1
        elif status >= SERVER_ERROR:
            server_errors += 1
        else:
            client_errors += 1
        took = record.get("ms", 0)
        if isinstance(took, int) and took > slowest:
            slowest = took
    return {
        "total": counted,
        "ok": ok,
        "client_errors": client_errors,
        "server_errors": server_errors,
        "slowest_ms": slowest,
    }
'''

SALES_BEFORE = '''
"""sales_report.py — the weekly regional report.

Input is the raw export from the ledger system: a header line, then one line per
sale. The export has carried a trailing blank line since 2024 and nobody has
ever fixed it, so the parser tolerates junk rather than trusting the file.
"""

REQUIRED = ("date", "region", "units")


def parse_rows(rows):
    """Header line plus data lines -> list of dicts. Unusable rows are dropped."""
    if not rows:
        return []
    header = [name.strip() for name in rows[0].split(",")]
    records = []
    for line in rows[1:]:
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(header):
            continue
        record = dict(zip(header, values))
        if any(name not in record for name in REQUIRED):
            continue
        records.append(record)
    return records


def units_of(record):
    """The units column as an integer, or None when it will not convert."""
    try:
        return int(record["units"])
    except (KeyError, ValueError):
        return None


def build_report(rows):
    """Units per region, biggest first, then a TOTAL line."""
    totals = {}
    for record in parse_rows(rows):
        units = units_of(record)
        if units is None:
            continue
        region = record["region"]
        totals[region] = totals.get(region, 0) + units

    order = sorted(totals, key=lambda region: (-totals[region], region))
    lines = [f"{region:<12}{totals[region]:>6}" for region in order]
    if rows:
        lines.append(f"{'TOTAL':<12}{sum(totals.values()):>6}")
    return lines
'''

SALES_AFTER = '''
"""sales_report.py — the weekly regional report.

Input is the raw export from the ledger system: a header line, then one line per
sale. The export has carried a trailing blank line since 2024 and nobody has
ever fixed it, so the parser tolerates junk rather than trusting the file.
"""

REQUIRED = ("date", "region", "units")


def parse_rows(rows):
    """Header line plus data lines -> list of dicts. Unusable rows are dropped."""
    if not rows:
        return []
    header = [name.strip() for name in rows[0].split(",")]
    records = []
    for line in rows[1:]:
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(header):
            continue
        record = dict(zip(header, values))
        if any(name not in record for name in REQUIRED):
            continue
        records.append(record)
    return records


def units_of(record):
    """The units column as an integer, or None when it will not convert."""
    try:
        return int(record["units"])
    except (KeyError, ValueError):
        return None


def in_range(date, since, until):
    """ISO dates sort lexicographically, so string comparison is the date
    comparison. That holds for YYYY-MM-DD and for nothing else."""
    if since is not None and date < since:
        return False
    if until is not None and date > until:
        return False
    return True


def build_report(rows, since=None, until=None):
    """Units per region, biggest first, then a TOTAL line.

    `since` and `until` are inclusive ISO dates; either may be None for
    unbounded.
    """
    totals = {}
    for record in parse_rows(rows):
        units = units_of(record)
        if units is None:
            continue
        if not in_range(record["date"], since, until):
            continue
        region = record["region"]
        totals[region] = totals.get(region, 0) + units

    order = sorted(totals, key=lambda region: (-totals[region], region))
    lines = [f"{region:<12}{totals[region]:>6}" for region in order]
    if rows:
        lines.append(f"{'TOTAL':<12}{sum(totals.values()):>6}")
    return lines
'''

SETTINGS_BEFORE = '''
"""settings.py — how the gateway decides what it is.

Layers, lowest priority first: packaged defaults, then the site file, then the
operator file. Each layer is a plain dict and the merge is deep, because half of
these settings live two levels down.

`freeze` below predates the move to dicts and is called from nowhere. It stays
because something in the test suite still imports it.
"""

DELETED = None          # a layer sets a key to None to remove it entirely


def deep_merge(base, extra):
    """`extra` laid over `base`. Neither input is modified."""
    merged = dict(base)
    for key, value in extra.items():
        if value is DELETED:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        elif isinstance(value, dict):
            merged[key] = deep_merge({}, value)
        else:
            merged[key] = value
    return merged


def freeze(config):
    """Old callers wanted a tuple of pairs. Nothing does any more."""
    return tuple(sorted((key, repr(value)) for key, value in config.items()))


def load_config(layers):
    """Fold the layers into one config, lowest priority first."""
    merged = {}
    for layer in layers:
        merged = deep_merge(merged, layer)
    return merged
'''

SETTINGS_AFTER = '''
"""settings.py — how the gateway decides what it is.

Layers, lowest priority first: packaged defaults, then the site file, then the
operator file, and finally the environment. Each layer is a plain dict and the
merge is deep, because half of these settings live two levels down.

`freeze` below predates the move to dicts and is called from nowhere. It stays
because something in the test suite still imports it.
"""

DELETED = None          # a layer sets a key to None to remove it entirely
ENV_PREFIX = "GATEWAY_"
ENV_NEST = "__"


def deep_merge(base, extra):
    """`extra` laid over `base`. Neither input is modified."""
    merged = dict(base)
    for key, value in extra.items():
        if value is DELETED:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        elif isinstance(value, dict):
            merged[key] = deep_merge({}, value)
        else:
            merged[key] = value
    return merged


def freeze(config):
    """Old callers wanted a tuple of pairs. Nothing does any more."""
    return tuple(sorted((key, repr(value)) for key, value in config.items()))


def coerce(raw):
    """An environment variable is always a string. Give it back its type."""
    lowered = raw.strip().lower()
    if lowered == "null":
        return DELETED
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(raw.strip())
    except ValueError:
        return raw


def env_layer(env):
    """The environment, as one more config layer to lay over the rest."""
    layer = {}
    for name in sorted(env):
        if not name.startswith(ENV_PREFIX):
            continue
        path = [part.lower() for part in name[len(ENV_PREFIX):].split(ENV_NEST)]
        if not all(path):
            continue                 # GATEWAY_, or a doubled separator
        branch = layer
        for part in path[:-1]:
            if not isinstance(branch.get(part), dict):
                branch[part] = {}
            branch = branch[part]
        branch[path[-1]] = coerce(env[name])
    return layer


def load_config(layers, env=None):
    """Fold the layers into one config, lowest priority first.

    The environment wins over every file layer.
    """
    merged = {}
    for layer in layers:
        merged = deep_merge(merged, layer)
    if env:
        merged = deep_merge(merged, env_layer(env))
    return merged
'''

ACCESS_RECORDS = [
    {"status": 200, "ms": 12},
    {"status": 404, "ms": 3},
    {"status": 503, "ms": 202},
    {"status": 200, "ms": 9},
    {"ms": 5},
    {"status": "200", "ms": 1},
]

SALES_EXPORT = [
    "date,region,units",
    "2026-03-01,north,12",
    "2026-03-02,south,7",
    "2026-03-09,north,5",
    "2026-03-10,east,nine",
    "2026-03-11,south,3",
    "",
]

DEFAULT_LAYER = {"timeout": 30, "log": {"level": "INFO", "sinks": ["stdout"]},
                 "limits": {"rps": 100}}
SITE_LAYER = {"timeout": 5, "log": {"level": "DEBUG"}}


def _ref_tally(events, exclude=()):
    skip = set(exclude)
    counts = {}
    for event in events:
        kind = event.get("kind")
        if kind is not None and kind not in skip:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def _ref_summarise(records):
    ok = client = server = slowest = counted = 0
    for record in records:
        status = record.get("status")
        if isinstance(status, bool) or not isinstance(status, int):
            continue
        counted += 1
        if status >= 500:
            server += 1
        elif status >= 400:
            client += 1
        else:
            ok += 1
        took = record.get("ms", 0)
        if isinstance(took, int) and took > slowest:
            slowest = took
    return {"total": counted, "ok": ok, "client_errors": client,
            "server_errors": server, "slowest_ms": slowest}


def _ref_build_report(rows, since=None, until=None):
    if not rows:
        return []
    header = [name.strip() for name in rows[0].split(",")]
    totals = {}
    for line in rows[1:]:
        values = [value.strip() for value in line.split(",")]
        if len(values) != len(header):
            continue
        record = dict(zip(header, values))
        if not all(name in record for name in ("date", "region", "units")):
            continue
        try:
            units = int(record["units"])
        except ValueError:
            continue
        if since is not None and record["date"] < since:
            continue
        if until is not None and record["date"] > until:
            continue
        totals[record["region"]] = totals.get(record["region"], 0) + units
    order = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    lines = ["%-12s%6d" % (region, total) for region, total in order]
    lines.append("%-12s%6d" % ("TOTAL", sum(totals.values())))
    return lines


def _ref_coerce(raw):
    lowered = raw.strip().lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw.strip())
    except ValueError:
        return raw


def _ref_load_config(layers, env=None):
    merged = {}
    for layer in list(layers) + ([_ref_env_layer(env)] if env else []):
        merged = _ref_deep(merged, layer)
    return merged


def _ref_env_layer(env):
    layer = {}
    for name in sorted(env):
        if not name.startswith("GATEWAY_"):
            continue
        path = [part.lower() for part in name[len("GATEWAY_"):].split("__")]
        if any(part == "" for part in path):
            continue
        node = layer
        for part in path[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[path[-1]] = _ref_coerce(env[name])
    return layer


def _ref_deep(base, extra):
    merged = dict(base)
    for key, value in extra.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict):
            current = merged.get(key)
            merged[key] = _ref_deep(current if isinstance(current, dict) else {}, value)
        else:
            merged[key] = value
    return merged


USAGE_MODULE = """
# usage.py — request accounting for the gateway.
# NOTE: samples were per-minute averages until the switch to per-request in March.


def summarise(samples):
    total = 0
    count = 0
    for sample in samples:
        if sample < 0:
            continue                 # the probe emits -1 when it times out
        total += sample
        count += 1
    return {
        "total": total,
        "count": count,
        "average": round(total / count, 2) if count else 0.0,
    }
"""


def _ref_usage(samples):
    kept = [s for s in samples if s >= 0]
    average = round(sum(kept) / len(kept), 2) if kept else 0.0
    return {"total": sum(kept), "count": len(kept), "average": average}


def featurework() -> list:
    return [
        guided(
            "pt-feature-average", "One More Key In The Dict",
            "`usage.py` already totals and counts the request samples, discarding "
            "the probe's -1 timeouts. Product wants the average in the same dict.\n\n"
            "Round it to two decimals. When nothing was counted the average is "
            "`0.0`, not a ZeroDivisionError and not None — the dashboard renders "
            "whatever it is given, and None renders as the word None.",
            "summarise", "samples", _ref_usage, USAGE_MODULE,
            [("round(total / count, 2) if count else 0.0",
              "the average, to two decimals, with the empty case answered")],
            [("four samples", [[10, 20, 30, 41]]),
             ("timeouts discarded", [[10, -1, 30]])],
            [("one sample", [[7]]),
             ("rounding", [[1, 1, 1]]),
             ("all timeouts", [[-1, -1]])],
            edges=[("no samples", [[]]), ("zeroes count", [[0, 0]])],
            pattern="SIMULATION", family="codebase_feature", realm="coding_coliseum",
            scaffold_for="ADDING A FIELD WITHOUT DISTURBING THE OTHERS",
            time="O(n)", space="O(1)",
            failures=["Dividing by `len(samples)` instead of `count`, which counts "
                      "the discarded timeouts",
                      "Letting the empty case raise instead of answering 0.0"],
            tags=["given-codebase"]),

        work("pt-feature-exclude", "An Argument That Was Not There",
             "`tally.py` counts events by kind. The quest log now needs to count "
             "everything EXCEPT a few kinds, and the caller wants to say which.\n\n"
             "Add an optional `exclude` parameter naming kinds to leave out of the "
             "result entirely. Every existing call site says `tally(events)` and "
             "must keep working unchanged — which tells you exactly what kind of "
             "parameter it has to be, and where it has to go." + GIVEN_NOTE,
             "tally", "events, exclude=()", _ref_tally, TALLY_AFTER,
             [("existing behaviour", [[{"kind": "login"}, {"kind": "quest"},
                                       {"kind": "login"}]]),
              ("one kind excluded", [[{"kind": "login"}, {"kind": "quest"}],
                                     ["login"]])],
             [("exclude a kind nobody has", [[{"kind": "a"}], ["b"]]),
              ("exclude everything", [[{"kind": "a"}, {"kind": "b"}], ["a", "b"]]),
              ("events with no kind still skipped", [[{"kind": "a"}, {"at": 1}],
                                                     ["b"]]),
              ("empty exclude behaves like none", [[{"kind": "a"}], []])],
             edges=[("no events", [[]]), ("no events, with exclude", [[], ["a"]])],
             difficulty="TUTORIAL", pattern="HASH_MAP", family="codebase_feature",
             realm="coding_coliseum", starter_code=TALLY_BEFORE,
             encounter="REFACTOR_QUEST",
             nudge="A parameter with a default is invisible to callers that do not "
                   "pass it. That is the whole mechanism.",
             pseudocode="def tally(events, exclude=()):\n  skip = set(exclude)\n"
                        "  ... skip kinds in `skip`",
             failures=["Making `exclude` positional, so every existing call breaks",
                       "`exclude=[]` as the default — a mutable default is shared "
                       "between calls forever",
                       "Filtering the result afterwards instead of skipping, which "
                       "is fine here and will not be once counting has side effects"],
             tags=["given-codebase", "add-feature"]),

        work("pt-feature-client-errors", "The Bucket Between The Buckets",
             "`gateway_report.py` counts responses as `ok` (under 400) or "
             "`server_errors` (500 and up). Everything from 400 to 499 is currently "
             "counted in `total` and nowhere else, which is how a week of broken "
             "auth looked like a quiet week.\n\n"
             "Add a `client_errors` key counting statuses 400 to 499 inclusive. "
             "`total`, `ok`, `server_errors` and `slowest_ms` must keep the values "
             "they have today.\n\n"
             "Note what `_status_of` already does about booleans. `True` is an "
             "`int` in Python, and a record whose status is `True` is not a "
             "successful request." + GIVEN_NOTE,
             "summarise", "records", _ref_summarise, GATEWAY_AFTER,
             [("a day of traffic", [ACCESS_RECORDS]),
              ("no client errors", [[{"status": 200, "ms": 1},
                                     {"status": 500, "ms": 2}]])],
             [("boundaries", [[{"status": 399}, {"status": 400}, {"status": 499},
                               {"status": 500}]]),
              ("status as a string is skipped", [[{"status": "404"}]]),
              ("boolean status is skipped", [[{"status": True}]]),
              ("missing ms", [[{"status": 404}]])],
             edges=[("no records", [[]]),
                    ("nothing countable", [[{"ms": 3}, {"status": None}]])],
             difficulty="EASY", pattern="SIMULATION", family="codebase_feature",
             realm="coding_coliseum", starter_code=GATEWAY_BEFORE,
             encounter="REFACTOR_QUEST", time="O(n)", space="O(1)",
             nudge="The existing if/elif already partitions the space. The new "
                   "bucket is the branch that is currently missing, not a second "
                   "pass over the records.",
             pseudocode="under 400 -> ok\n500 and up -> server\notherwise -> client",
             failures=["A separate `if 400 <= status < 500` after the elif chain, "
                       "which works and then drifts the next time somebody edits "
                       "one of the two",
                       "Changing `< 400` to `<= 400` and moving 400 into `ok`",
                       "Counting client errors in `total` twice"],
             tags=["given-codebase", "add-feature"]),

        work("pt-feature-date-range", "Only This Week, Please",
             "`sales_report.py` reports units per region across the whole export. "
             "Finance wants it for a date range.\n\n"
             "Add optional `since` and `until` parameters — inclusive ISO dates, "
             "either one `None` for unbounded — that filter on the `date` column "
             "before anything is totalled. `build_report(rows)` with no bounds must "
             "produce exactly what it produces today, including the TOTAL line for "
             "a non-empty file that has no usable rows in it.\n\n"
             "ISO dates compare correctly as strings. Say so in a comment, because "
             "the reviewer is about to ask, and the answer is `YYYY-MM-DD sorts "
             "lexicographically and no other date format does`." + GIVEN_NOTE,
             "build_report", "rows, since=None, until=None", _ref_build_report,
             SALES_AFTER,
             [("whole export", [SALES_EXPORT]),
              ("one week", [SALES_EXPORT, "2026-03-09", "2026-03-11"])],
             [("since only", [SALES_EXPORT, "2026-03-10"]),
              ("until only", [SALES_EXPORT, None, "2026-03-02"]),
              ("range excludes everything", [SALES_EXPORT, "2027-01-01"]),
              ("bounds are inclusive", [SALES_EXPORT, "2026-03-01", "2026-03-01"]),
              ("malformed row still dropped", [SALES_EXPORT, "2026-03-10",
                                               "2026-03-10"])],
             edges=[("empty file", [[]]),
                    ("header only", [[SALES_EXPORT[0]], "2026-01-01"])],
             difficulty="MEDIUM", pattern="SORTING", family="codebase_feature",
             realm="coding_coliseum", starter_code=SALES_BEFORE,
             encounter="REFACTOR_QUEST", time="O(n log n)",
             secondary=["HASH_MAP", "STRING"],
             nudge="One predicate, applied where the row is already being inspected. "
                   "Resist adding a second pass over the rows.",
             pseudocode=("def build_report(rows, since=None, until=None):\n"
                         "  ... skip record unless in_range(record['date'], since, until)"),
             failures=["Filtering after totalling, which totals the rows you meant "
                       "to exclude",
                       "Making the bounds exclusive when the statement said inclusive",
                       "Dropping the TOTAL line when the filter empties the report — "
                       "that is existing behaviour and it was not yours to change",
                       "Parsing the dates with `strptime` when the file is already "
                       "in the one format where you do not have to"],
             tags=["given-codebase", "add-feature"],
             source_type="GENERAL_INTERVIEW",
             provenance="'Add this option to the existing report' is the reported "
                        "shape of the practical exercise."),

        work("pt-feature-env-overrides", "The Environment Wins",
             "`settings.py` folds config layers, lowest priority first, and a layer "
             "setting a key to `None` deletes it. Containers do not ship files, so "
             "the gateway now has to take overrides from environment variables.\n\n"
             "Add an optional `env` parameter — a dict of environment variables — "
             "applied as one final layer, over everything. The rules:\n\n"
             "- only names starting with `GATEWAY_` are considered; everything else "
             "in the environment is somebody else's;\n"
             "- strip the prefix, lowercase the rest, and split nesting on `__`, so "
             "`GATEWAY_LOG__LEVEL` sets `config[\"log\"][\"level\"]`;\n"
             "- values are strings, so give them their types back: `true`/`false` "
             "in any case become booleans, an integer becomes an `int`, `null` "
             "becomes the existing delete-this-key sentinel, anything else stays a "
             "string;\n"
             "- a name that produces an empty path segment (`GATEWAY_`, or a "
             "doubled separator) is ignored rather than fatal;\n"
             "- process the names in sorted order, so two overrides that collide "
             "resolve the same way on every machine.\n\n"
             "`load_config(layers)` with no environment must behave exactly as it "
             "does today." + GIVEN_NOTE,
             "load_config", "layers, env=None", _ref_load_config, SETTINGS_AFTER,
             [("no environment", [[DEFAULT_LAYER, SITE_LAYER]]),
              ("one scalar override", [[DEFAULT_LAYER], {"GATEWAY_TIMEOUT": "5"}])],
             [("nested override", [[DEFAULT_LAYER],
                                   {"GATEWAY_LOG__LEVEL": "DEBUG"}]),
              ("types come back", [[DEFAULT_LAYER],
                                   {"GATEWAY_DEBUG": "true",
                                    "GATEWAY_LIMITS__RPS": "250",
                                    "GATEWAY_NAME": "edge-01"}]),
              ("null deletes", [[DEFAULT_LAYER], {"GATEWAY_TIMEOUT": "null"}]),
              ("other variables ignored", [[DEFAULT_LAYER],
                                           {"PATH": "/usr/bin", "HOME": "/root"}]),
              ("empty segment ignored", [[DEFAULT_LAYER],
                                         {"GATEWAY_": "x", "GATEWAY_A__": "y"}]),
              ("env beats every file layer", [[DEFAULT_LAYER, SITE_LAYER],
                                              {"GATEWAY_TIMEOUT": "1"}]),
              ("deep branch created", [[{}], {"GATEWAY_A__B__C": "deep"}]),
              ("false is a boolean, not a string", [[{}],
                                                    {"GATEWAY_VERIFY": "False"}]),
              ("negative integer", [[{}], {"GATEWAY_OFFSET": "-3"}])],
             edges=[("no layers and no env", [[]]),
                    ("empty env dict", [[DEFAULT_LAYER], {}]),
                    ("override lands on a non-dict", [[{"log": "off"}],
                                                      {"GATEWAY_LOG__LEVEL": "INFO"}])],
             difficulty="HARD", pattern="HASH_MAP", family="codebase_feature",
             realm="coding_coliseum", starter_code=SETTINGS_BEFORE,
             encounter="REFACTOR_QUEST", secondary=["STRING", "RECURSION"],
             nudge="Build the environment into a config layer, then hand it to the "
                   "`deep_merge` that already exists. Do not write a second merge.",
             pseudocode=("env_layer(env):\n"
                         "  for name in sorted(env):\n"
                         "    skip unless it starts with the prefix\n"
                         "    path = prefix-stripped, lowercased, split on '__'\n"
                         "    skip if any segment is empty\n"
                         "    walk/create dicts down to the last segment\n"
                         "    assign coerce(value)\n"
                         "load_config: fold layers, then merge env_layer if env"),
             failures=["Writing a second merge instead of reusing `deep_merge`, so "
                       "the delete sentinel stops working inside env overrides",
                       "`bool('false')` is True — string to boolean needs an explicit "
                       "comparison",
                       "`int(value)` without a try, which turns every non-numeric "
                       "override into a crash at startup",
                       "Iterating `env` in dict order, which is insertion order and "
                       "therefore different on every host",
                       "Descending into `config['log']` when it holds a string, and "
                       "raising instead of replacing it"],
             tags=["given-codebase", "add-feature"],
             source_type="GENERAL_INTERVIEW",
             provenance="Extending an existing loader with environment overrides is "
                        "a widely reported practical task."),
    ]


# ---------------------------------------------------------------------------
# 10. Find and fix a bug in a module you did not write
# ---------------------------------------------------------------------------
#
# Every one of these hands over the failing test with the module. That is the
# realistic version: in the exercise, and at work, you are almost never told
# where the bug is — you are told what came out wrong, and the first move is
# always to run it and read the difference.

SLO_LOG = [
    "2026-03-10T09:14:02 INFO GET /v1/session 200 12",
    "2026-03-10T09:14:03 ERROR POST /v1/login 500 118",
    "2026-03-10T09:14:0",                                 # rotated mid-write
    "2026-03-10T09:15:01 INFO GET /v1/session 200 9",
    "2026-03-10T09:15:44 WARN GET /v1/keys 404 3",
]


def _ref_data_name(filename):
    return filename[:-4] if filename.endswith(".csv") else filename


def _ref_with_defaults(settings):
    merged = {"retries": 3, "timeout": 30}
    merged.update(settings)
    return merged


def _ref_batches(items, size):
    if size <= 0:
        return []
    return [items[start:start + size] for start in range(0, len(items), size)]


def _ref_group_ids(records, statuses):
    buckets = {status: [] for status in statuses}
    for record in records:
        status = record.get("status")
        if status in buckets:
            buckets[status].append(record.get("id"))
    return buckets


def _ref_availability(lines):
    parsed = []
    for line in lines:
        fields = line.split()
        if len(fields) != 6:
            continue
        try:
            parsed.append((int(fields[4]), int(fields[5])))
        except ValueError:
            continue
    counted = len(parsed)
    errors = sum(1 for status, _ in parsed if status >= 500)
    slowest = max((ms for _, ms in parsed), default=0)
    rate = round(100.0 * errors / counted, 1) if counted else 0.0
    return {"counted": counted, "errors": errors, "error_rate": rate,
            "slowest_ms": slowest}


def bugwork() -> list:
    return [
        debug_problem(
            id="pt-bug-suffix", title="The Suffix That Ate The Name",
            difficulty="GUIDED", realm="debugging_dungeon", family="debugging",
            statement="""
            The report titles are wrong for exactly one customer. Here is the
            failing test:

                data_name("csv.csv")  ->  ""      (expected "csv")

            The function has one line. `str.strip` takes a SET of characters and
            removes any of them from BOTH ends, repeatedly — it is not a suffix
            removal, it has never been a suffix removal, and it looks like one.

            Fix the line. Names that do not end in `.csv` come back untouched.
            """,
            fn_name="data_name", params="filename",
            broken="""
            def data_name(filename):
                \"\"\"'sales.csv' -> 'sales'. Used to title the report.\"\"\"
                return filename.strip(".csv")
            """,
            canonical="""
            def data_name(filename):
                \"\"\"'sales.csv' -> 'sales'. Used to title the report.\"\"\"
                return filename.removesuffix(".csv")
            """,
            reference=_ref_data_name,
            visible=[("ordinary name", ["sales.csv"]),
                     ("the failing case", ["csv.csv"])],
            hidden=[("not a csv", ["notes.txt"]),
                    ("no extension", ["sales"]),
                    ("letters from the set at the front", ["scv.csv"]),
                    ("empty", [""])],
            bug_type="api-misuse", armor_piece="helmet",
            time_complexity="O(n)", space_complexity="O(n)",
            nudge="Read the docstring of `str.strip`. Then read the name of the "
                  "method that does what you actually meant.",
            failures=["`strip('.csv')` removes any of `.`, `c`, `s`, `v` from both "
                      "ends until it runs out",
                      "`rstrip('.csv')` is the same bug facing one direction",
                      "`replace('.csv', '')` also removes it from the middle"],
        ),

        debug_problem(
            id="pt-bug-shared-defaults", title="The Dict That Remembered",
            difficulty="TUTORIAL", realm="debugging_dungeon", family="debugging",
            statement="""
            Settings are right on the first request of the process and wrong on
            every one after it. The failing test, run twice in the same process:

                with_defaults({"timeout": 5})   ->  {"retries": 3, "timeout": 5}
                with_defaults({"retries": 1})   ->  {"retries": 1, "timeout": 5}

            The second call inherits the first caller's timeout. Nothing stored
            it anywhere — except that something did.

            One line is wrong. Fix it so `DEFAULTS` is still there, unchanged,
            after any number of calls.
            """,
            fn_name="with_defaults", params="settings",
            broken="""
            DEFAULTS = {"retries": 3, "timeout": 30}


            def with_defaults(settings):
                \"\"\"Caller settings laid over the packaged defaults.\"\"\"
                merged = DEFAULTS
                merged.update(settings)
                return merged
            """,
            canonical="""
            DEFAULTS = {"retries": 3, "timeout": 30}


            def with_defaults(settings):
                \"\"\"Caller settings laid over the packaged defaults.\"\"\"
                merged = dict(DEFAULTS)      # a copy: DEFAULTS belongs to the module
                merged.update(settings)
                return merged
            """,
            reference=_ref_with_defaults,
            visible=[("first call", [{"timeout": 5}]),
                     ("second call sees the damage", [{"retries": 1}])],
            hidden=[("empty settings", [{}]),
                    ("a new key", [{"verify": False}]),
                    ("overrides both", [{"retries": 9, "timeout": 9}]),
                    ("empty again, much later", [{}])],
            bug_type="shared-mutable-state", armor_piece="chestplate",
            time_complexity="O(n)", space_complexity="O(n)",
            nudge="`merged = DEFAULTS` does not make a dict. It makes a second name "
                  "for the one dict there has ever been.",
            failures=["Assignment never copies a container in Python; it binds a name",
                      "`DEFAULTS.copy()` and `dict(DEFAULTS)` both fix it; a nested "
                      "default would need `copy.deepcopy`",
                      "`{**DEFAULTS, **settings}` fixes it and removes the mutation "
                      "entirely"],
        ),

        debug_problem(
            id="pt-bug-last-batch", title="The Batch That Never Shipped",
            difficulty="EASY", realm="debugging_dungeon", family="debugging",
            statement="""
            The uploader sends items in batches of `size`. Someone noticed that
            the last few items of every import are missing. The failing test:

                batches([1, 2, 3, 4, 5, 6, 7], 3)
                  ->  [[1, 2, 3], [4, 5, 6]]
                  expected [[1, 2, 3], [4, 5, 6], [7]]

            Worse, an exact multiple loses a whole batch. One expression is
            wrong. The guard for a non-positive size is correct and stays.
            """,
            fn_name="batches", params="items, size",
            broken="""
            def batches(items, size):
                \"\"\"Split items into batches of `size`. The last batch may be short.\"\"\"
                if size <= 0:
                    return []
                out = []
                for start in range(0, len(items) - size, size):
                    out.append(items[start:start + size])
                return out
            """,
            canonical="""
            def batches(items, size):
                \"\"\"Split items into batches of `size`. The last batch may be short.\"\"\"
                if size <= 0:
                    return []
                out = []
                for start in range(0, len(items), size):
                    out.append(items[start:start + size])
                return out
            """,
            reference=_ref_batches,
            visible=[("the failing case", [[1, 2, 3, 4, 5, 6, 7], 3]),
                     ("exact multiple", [[1, 2, 3, 4, 5, 6], 3])],
            hidden=[("size larger than the input", [[1, 2], 5]),
                    ("size of one", [[1, 2, 3], 1]),
                    ("empty input", [[], 3]),
                    ("size zero", [[1, 2, 3], 0]),
                    ("negative size", [[1, 2, 3], -2])],
            bug_type="off-by-one", armor_piece="boots",
            time_complexity="O(n)", space_complexity="O(n)",
            nudge="Write out `range(0, len(items) - size, size)` for a seven-item "
                  "list by hand. Where does it stop, and where should it stop?",
            failures=["Slicing past the end of a list is safe in Python — "
                      "`items[6:9]` is `[7]`, not an error, so the range never "
                      "needed the `- size` at all",
                      "Fixing it with `+ size - 1`, which produces a spurious empty "
                      "batch on an exact multiple"],
        ),

        debug_problem(
            id="pt-bug-shared-buckets", title="Every Bucket, The Same Bucket",
            difficulty="MEDIUM", realm="debugging_dungeon", family="debugging",
            statement="""
            The triage view shows every status holding every request. The
            failing test:

                group_ids([{"id": "a", "status": 200},
                           {"id": "b", "status": 500}], [200, 500])
                  ->  {200: ["a", "b"], 500: ["a", "b"]}
                  expected {200: ["a"], 500: ["b"]}

            The counting loop is right. The routing is right. Something built
            before the loop is wrong, and it is one line.

            `dict.fromkeys(keys, value)` evaluates `value` ONCE and gives every
            key that same object. For an integer that is invisible. For a list it
            is this.
            """,
            fn_name="group_ids", params="records, statuses",
            broken="""
            \"\"\"triage.py — which requests landed in which status bucket.

            Only the statuses the caller asks about get a bucket; everything else
            is somebody else's dashboard.
            \"\"\"


            def known(record, statuses):
                \"\"\"Kept from the pilot. Nothing calls it now.\"\"\"
                return record.get("status") in set(statuses)


            def group_ids(records, statuses):
                \"\"\"Bucket record ids by status, one bucket per requested status.\"\"\"
                buckets = dict.fromkeys(statuses, [])
                for record in records:
                    status = record.get("status")
                    if status in buckets:
                        buckets[status].append(record.get("id"))
                return buckets
            """,
            canonical="""
            \"\"\"triage.py — which requests landed in which status bucket.

            Only the statuses the caller asks about get a bucket; everything else
            is somebody else's dashboard.
            \"\"\"


            def known(record, statuses):
                \"\"\"Kept from the pilot. Nothing calls it now.\"\"\"
                return record.get("status") in set(statuses)


            def group_ids(records, statuses):
                \"\"\"Bucket record ids by status, one bucket per requested status.\"\"\"
                # One fresh list per key. fromkeys would hand out one list, shared.
                buckets = {status: [] for status in statuses}
                for record in records:
                    status = record.get("status")
                    if status in buckets:
                        buckets[status].append(record.get("id"))
                return buckets
            """,
            reference=_ref_group_ids,
            visible=[("the failing case", [[{"id": "a", "status": 200},
                                            {"id": "b", "status": 500}], [200, 500]]),
                     ("one bucket only", [[{"id": "a", "status": 200}], [200]])],
            hidden=[("status nobody asked about", [[{"id": "a", "status": 404}],
                                                   [200, 500]]),
                    ("record with no status", [[{"id": "a"}], [200]]),
                    ("record with no id", [[{"status": 200}], [200]]),
                    ("no records", [[], [200, 500]]),
                    ("no statuses", [[{"id": "a", "status": 200}], []])],
            bug_type="aliasing", armor_piece="shield",
            time_complexity="O(n)", space_complexity="O(n)",
            nudge="Ask whether `buckets[200]` and `buckets[500]` are two lists or "
                  "one list with two names. `is` will tell you in one line.",
            failures=["`dict.fromkeys(keys, [])` shares one list across every key",
                      "`defaultdict(list)` also fixes it but changes the contract: "
                      "the caller asked for a bucket per requested status, present "
                      "even when empty",
                      "Copying the dict afterwards does not help — the lists inside "
                      "are still the same list"],
        ),

        debug_problem(
            id="pt-bug-denominator", title="The Number On The Status Page",
            difficulty="HARD", realm="debugging_dungeon", family="debugging",
            statement="""
            `slo.py` produces the availability number the company publishes. It
            has been slightly optimistic for a year, and only on days when the
            log rotated mid-write.

            The failing test — a five-line log with one torn line in it:

                availability(SLO_LOG)["error_rate"]  ->  20.0
                                              expected 25.0

            Four lines parsed. One of those four was a 500. That is 25%, and the
            module says 20%, which is one error over five.

            The parser is correct — a torn line SHOULD be skipped. Every counter
            in the loop is correct. One expression after the loop divides by the
            wrong thing. Fix that expression and leave the rest alone, including
            the zero case: a file with nothing readable in it reports `0.0`, not
            a ZeroDivisionError.
            """,
            fn_name="availability", params="lines",
            broken='''
            """slo.py — the availability number that goes on the status page.

            Consumes the gateway's own access log:

                TIMESTAMP LEVEL METHOD PATH STATUS MS

            Lines that are not six fields, or whose status and duration will not
            convert, are unreadable and are skipped: the log rotates mid-write
            about once a week and we would rather publish a number than crash.
            """

            SERVER_ERROR = 500

            # From the pilot, when the status page showed a letter grade.
            GRADES = ((99.9, "A"), (99.0, "B"), (95.0, "C"))


            def parse(line):
                """One line -> [status, ms], or None when the line is unreadable."""
                fields = line.split()
                if len(fields) != 6:
                    return None
                try:
                    return [int(fields[4]), int(fields[5])]
                except ValueError:
                    return None


            def availability(lines):
                """Requests counted, server errors seen, and the error rate."""
                counted = 0
                errors = 0
                slowest = 0
                for line in lines:
                    parsed = parse(line)
                    if parsed is None:
                        continue
                    status, took = parsed
                    counted += 1
                    if status >= SERVER_ERROR:
                        errors += 1
                    if took > slowest:
                        slowest = took
                rate = round(100.0 * errors / len(lines), 1) if lines else 0.0
                return {"counted": counted, "errors": errors,
                        "error_rate": rate, "slowest_ms": slowest}
            ''',
            canonical='''
            """slo.py — the availability number that goes on the status page.

            Consumes the gateway's own access log:

                TIMESTAMP LEVEL METHOD PATH STATUS MS

            Lines that are not six fields, or whose status and duration will not
            convert, are unreadable and are skipped: the log rotates mid-write
            about once a week and we would rather publish a number than crash.
            """

            SERVER_ERROR = 500

            # From the pilot, when the status page showed a letter grade.
            GRADES = ((99.9, "A"), (99.0, "B"), (95.0, "C"))


            def parse(line):
                """One line -> [status, ms], or None when the line is unreadable."""
                fields = line.split()
                if len(fields) != 6:
                    return None
                try:
                    return [int(fields[4]), int(fields[5])]
                except ValueError:
                    return None


            def availability(lines):
                """Requests counted, server errors seen, and the error rate."""
                counted = 0
                errors = 0
                slowest = 0
                for line in lines:
                    parsed = parse(line)
                    if parsed is None:
                        continue
                    status, took = parsed
                    counted += 1
                    if status >= SERVER_ERROR:
                        errors += 1
                    if took > slowest:
                        slowest = took
                # The rate is errors per REQUEST COUNTED. Lines we could not read
                # are not requests that succeeded; they are not requests at all.
                rate = round(100.0 * errors / counted, 1) if counted else 0.0
                return {"counted": counted, "errors": errors,
                        "error_rate": rate, "slowest_ms": slowest}
            ''',
            reference=_ref_availability,
            visible=[("the failing case", [SLO_LOG]),
                     ("a clean log", [SLO_LOG[:2] + SLO_LOG[3:]])],
            hidden=[("nothing readable", [["torn", "also torn"]]),
                    ("no errors at all", [[SLO_LOG[0], SLO_LOG[3]]]),
                    ("every request failed", [[SLO_LOG[1]]]),
                    ("status is not a number", [[
                        "2026-03-10T09:14:02 INFO GET /v1/x abc 5"]]),
                    ("no lines", [[]]),
                    ("rounding to one decimal", [[SLO_LOG[1]] + [SLO_LOG[0]] * 2])],
            bug_type="wrong-denominator", armor_piece="legendary",
            time_complexity="O(n)", space_complexity="O(1)",
            nudge="The loop tracks two totals and the division uses a third number "
                  "that the loop never computed. Which of the three is the "
                  "denominator the docstring describes?",
            failures=["`len(lines)` counts lines, and the whole module is built "
                      "around lines that are not requests",
                      "Changing `parse` to keep the torn lines, which fixes the "
                      "percentage by corrupting the count",
                      "Removing the zero guard along with the bug, which trades a "
                      "wrong number for a crash on an empty file"],
        ),
    ]


# ---------------------------------------------------------------------------
# 11. Extend a class you did not write
# ---------------------------------------------------------------------------
#
# The reference classes below are independent re-implementations, exactly as the
# reference functions elsewhere are. The canonical module and the reference class
# have to agree on every operation trace or the problem does not ship.

class _RefEventLog:
    def __init__(self):
        self._events = []

    def add(self, kind, at):
        self._events.append((kind, at))
        return len(self._events)

    def kinds(self):
        return sorted({kind for kind, _ in self._events})

    def count(self, kind):
        return [k for k, _ in self._events].count(kind)

    def latest(self, kind):
        found = [at for k, at in self._events if k == kind]
        return found[-1] if found else None


class _RefLedger:
    def __init__(self):
        self._totals = {}
        self._entries = 0

    def post(self, account, amount):
        self._totals[account] = self._totals.get(account, 0) + amount
        self._entries += 1
        return self._totals[account]

    def balance(self, account):
        return self._totals.get(account, 0)

    def accounts(self):
        return sorted(self._totals)

    def biggest(self, n):
        ranked = sorted(self._totals.items(), key=lambda item: (-item[1], item[0]))
        return [[account, total] for account, total in ranked[:max(n, 0)]]


class _RefRecentCache:
    def __init__(self, capacity):
        self._capacity = capacity
        self._order = []
        self._values = {}

    def put(self, key, value):
        evicted = None
        if key in self._values:
            self._order.remove(key)
        elif len(self._values) >= self._capacity:
            evicted = self._order.pop(0)
            del self._values[evicted]
        self._order.append(key)
        self._values[key] = value
        return evicted

    def get(self, key):
        return self._values.get(key)

    def keys(self):
        return list(self._order)

    def touch(self, key):
        if key not in self._values:
            return False
        self._order.remove(key)
        self._order.append(key)
        return True


class _RefConfigStore:
    def __init__(self, defaults=None):
        self._values = dict(defaults or {})
        self._changes = []

    def set(self, key, value):
        previous = self._values.get(key)
        self._values[key] = value
        self._changes.append((key, previous, value))
        return previous

    def get(self, key, default=None):
        return self._values.get(key, default)

    def history(self, key):
        return [[previous, new] for k, previous, new in self._changes if k == key]

    def apply(self, updates):
        if not all(isinstance(key, str) for key in updates):
            return False
        for key in sorted(updates):
            self.set(key, updates[key])
        return True


EVENT_LOG_AFTER = '''
class EventLog:
    """Every event the quest log has seen, in arrival order.

    Small on purpose. The dashboard reads it once a second and nothing else
    touches it.
    """

    def __init__(self):
        self.events = []

    def add(self, kind, at):
        """Record one event. Returns how many events are now held."""
        self.events.append({"kind": kind, "at": at})
        return len(self.events)

    def kinds(self):
        """Every kind seen, sorted, without repeats."""
        return sorted({event["kind"] for event in self.events})

    def count(self, kind):
        """How many events of this kind have been recorded."""
        return sum(1 for event in self.events if event["kind"] == kind)

    def latest(self, kind):
        """The `at` of the most recent event of this kind, or None."""
        for event in reversed(self.events):
            if event["kind"] == kind:
                return event["at"]
        return None
'''

LEDGER_BEFORE = '''
class Ledger:
    """Running totals per account.

    Written during the billing spike and never cleaned up. `entries` is only
    read by a log line that is currently commented out.
    """

    def __init__(self):
        self.totals = {}
        self.entries = 0

    def post(self, account, amount):
        """Add `amount` to `account`. Returns the account's new total."""
        self.totals[account] = self.totals.get(account, 0) + amount
        self.entries += 1
        return self.totals[account]

    def balance(self, account):
        """The account's total. Zero if it has never been posted to."""
        return self.totals.get(account, 0)

    def accounts(self):
        """Every account that has ever been posted to, sorted."""
        return sorted(self.totals)
'''

LEDGER_AFTER = LEDGER_BEFORE.rstrip() + '''

    def biggest(self, n):
        """The `n` largest accounts as [account, total] pairs.

        Ordered by total descending, then by account name ascending. Asking for
        more than there are returns all of them.
        """
        ranked = sorted(self.totals.items(),
                        key=lambda item: (-item[1], item[0]))
        return [[account, total] for account, total in ranked[:max(n, 0)]]
'''

CACHE_BEFORE = '''
class RecentCache:
    """A fixed-size cache that evicts the OLDEST key, not the least used.

    FIFO, deliberately: the workload is a replay buffer, and reads are not
    supposed to keep an entry alive. `capacity` is at least 1.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.order = []            # keys, oldest first
        self.values = {}

    def put(self, key, value):
        """Store a value. Returns the key that was evicted, or None."""
        evicted = None
        if key in self.values:
            self.order.remove(key)
        elif len(self.values) >= self.capacity:
            evicted = self.order.pop(0)
            del self.values[evicted]
        self.order.append(key)
        self.values[key] = value
        return evicted

    def get(self, key):
        """The stored value, or None. Reading does not change the order."""
        return self.values.get(key)

    def keys(self):
        """The live keys, oldest first."""
        return list(self.order)
'''

CACHE_AFTER = CACHE_BEFORE.rstrip() + '''

    def touch(self, key):
        """Make `key` the youngest entry, so it is evicted last.

        Returns True when the key was present, False when it was not. A missing
        key is not stored and not an error.
        """
        if key not in self.values:
            return False
        self.order.remove(key)
        self.order.append(key)
        return True
'''

STORE_BEFORE = '''
class ConfigStore:
    """Flat settings with a change log.

    Every write is recorded so the support team can answer "when did this
    change". The log is never trimmed, which is fine at the current write rate
    and will not be forever.
    """

    def __init__(self, defaults=None):
        self.values = dict(defaults or {})
        self.changes = []

    def set(self, key, value):
        """Set a key. Returns the value it had before, or None."""
        previous = self.values.get(key)
        self.values[key] = value
        self.changes.append([key, previous, value])
        return previous

    def get(self, key, default=None):
        """The current value, or `default`."""
        return self.values.get(key, default)

    def history(self, key):
        """Every change to this key, oldest first, as [previous, new] pairs."""
        return [[previous, new] for k, previous, new in self.changes if k == key]
'''

STORE_AFTER = STORE_BEFORE.rstrip() + '''

    def apply(self, updates):
        """Set many keys at once, or none of them.

        Every key must be a string. If any is not, nothing is written, nothing
        is logged, and the call returns False. Otherwise the keys are set in
        sorted order — so the change log is identical on every machine — and the
        call returns True.
        """
        # Validate the whole batch BEFORE touching anything. Half-applied
        # config is worse than rejected config, and sorted() on mixed key types
        # raises anyway, which would leave exactly that mess behind.
        if not all(isinstance(key, str) for key in updates):
            return False
        for key in sorted(updates):
            self.set(key, updates[key])
        return True
'''


def classwork() -> list:
    return [
        extend_class(
            "pt-class-latest", "The Method That Was Missing",
            "SCAFFOLD — ADDING A METHOD TO SOMEBODY ELSE'S CLASS\n\n"
            "`EventLog` records events and can already count them. The quest log "
            "now needs `latest(kind)`: the `at` of the MOST RECENT event of that "
            "kind, or `None` when there has never been one.\n\n"
            "The method is written for you except one expression. Events are held "
            "in arrival order, so the most recent match is the LAST one — and "
            "walking from the end and returning the first hit beats scanning the "
            "whole list and keeping the last.\n\n"
            "Every `__BLANK__` is exactly one expression. Change nothing else.",
            "EventLog", _RefEventLog, EVENT_LOG_AFTER, "",
            [("record and read back",
              ["__init__", "add", "add", "count", "latest"],
              [[], ["login", 100], ["quest", 140], ["login"], ["login"]]),
             ("two of a kind, newest wins",
              ["__init__", "add", "add", "latest"],
              [[], ["login", 100], ["login", 200], ["login"]])],
            [("kind never seen",
              ["__init__", "add", "latest"], [[], ["login", 1], ["quest"]]),
             ("empty log",
              ["__init__", "latest", "kinds"], [[], ["login"], []]),
             ("interleaved kinds",
              ["__init__", "add", "add", "add", "latest", "latest"],
              [[], ["a", 1], ["b", 2], ["a", 3], ["a"], ["b"]])],
            edges=[("nothing recorded at all",
                    ["__init__", "count", "latest"], [[], ["x"], ["x"]])],
            difficulty="GUIDED", family="codebase_class",
            blanks=[("reversed(self.events)",
                     "walk the events newest-first, so the first match is the answer")],
            nudge="`reversed()` gives you the list backwards without copying it or "
                  "disturbing it.",
            failures=["`self.events[::-1]` also works and copies the whole list",
                      "Scanning forwards and returning the first match gives you the "
                      "OLDEST event of that kind"],
            tags=["add-feature"]),

        extend_class(
            "pt-class-biggest", "The Top Of The Ledger",
            "`Ledger` keeps a running total per account. The finance view needs "
            "`biggest(n)`: the `n` largest accounts as `[account, total]` pairs, "
            "ordered by total descending and then by account name ascending.\n\n"
            "Asking for more accounts than exist returns all of them. Asking for "
            "zero or fewer returns an empty list. Do not change `post`, `balance` "
            "or `accounts` — other code calls all three.",
            "Ledger", _RefLedger, LEDGER_AFTER, LEDGER_BEFORE,
            [("three accounts",
              ["__init__", "post", "post", "post", "biggest"],
              [[], ["ops", 40], ["dev", 90], ["ops", 30], [2]]),
             ("existing behaviour still works",
              ["__init__", "post", "balance", "accounts"],
              [[], ["ops", 5], ["ops"], []])],
            [("tie broken by name",
              ["__init__", "post", "post", "biggest"],
              [[], ["zeta", 10], ["alpha", 10], [2]]),
             ("more than there are",
              ["__init__", "post", "biggest"], [[], ["ops", 1], [99]]),
             ("zero requested",
              ["__init__", "post", "biggest"], [[], ["ops", 1], [0]]),
             ("negative totals rank last",
              ["__init__", "post", "post", "biggest"],
              [[], ["a", -5], ["b", 1], [2]])],
            edges=[("nothing posted", ["__init__", "biggest"], [[], [3]]),
                   ("negative n", ["__init__", "post", "biggest"],
                    [[], ["a", 1], [-1]])],
            difficulty="TUTORIAL", family="codebase_class",
            nudge="`sorted(self.totals.items(), key=...)` with a two-part key, then "
                  "slice. The slice handles `n` larger than the dict on its own.",
            pseudocode="ranked = sorted(items, key=(-total, account))\n"
                       "return [[a, t] for a, t in ranked[:n]]",
            failures=["`sorted(...)[:n]` with a negative `n` silently drops from the "
                      "END of the list instead of returning nothing",
                      "Sorting by total alone, so ties come out in dict order",
                      "Returning tuples where the caller and the tests expect lists"],
            tags=["add-feature"]),

        extend_class(
            "pt-class-touch", "One Step Towards LRU",
            "`RecentCache` evicts the oldest key. That is deliberate — read the "
            "docstring before you 'fix' `get`.\n\n"
            "The replay buffer now needs `touch(key)`: make that key the youngest, "
            "so it is evicted last. Return True when the key was present and False "
            "when it was not. A missing key is not inserted and is not an error.\n\n"
            "The invariant you must not break: `order` and `values` hold exactly "
            "the same keys, and `order` is oldest-first. `put`, `get` and `keys` "
            "keep their current behaviour — `get` still does NOT reorder anything.",
            "RecentCache", _RefRecentCache, CACHE_AFTER, CACHE_BEFORE,
            [("touch then evict",
              ["__init__", "put", "put", "touch", "put", "keys"],
              [[2], ["a", 1], ["b", 2], ["a"], ["c", 3], []]),
             ("eviction without touching is still FIFO",
              ["__init__", "put", "put", "put", "keys"],
              [[2], ["a", 1], ["b", 2], ["c", 3], []])],
            [("touch a missing key",
              ["__init__", "put", "touch", "keys"], [[2], ["a", 1], ["zz"], []]),
             ("touch the only key",
              ["__init__", "put", "touch", "keys"], [[2], ["a", 1], ["a"], []]),
             ("get does not reorder",
              ["__init__", "put", "put", "get", "put", "keys"],
              [[2], ["a", 1], ["b", 2], ["a"], ["c", 3], []]),
             ("overwrite keeps one copy",
              ["__init__", "put", "put", "keys"], [[2], ["a", 1], ["a", 9], []]),
             ("touch twice",
              ["__init__", "put", "put", "touch", "touch", "keys"],
              [[2], ["a", 1], ["b", 2], ["a"], ["a"], []])],
            edges=[("touch an empty cache",
                    ["__init__", "touch", "keys"], [[1], ["a"], []]),
                   ("capacity of one",
                    ["__init__", "put", "put", "keys"], [[1], ["a", 1], ["b", 2], []])],
            difficulty="EASY", family="codebase_class",
            nudge="`put` already knows how to move an existing key to the young end. "
                  "Do what it does, and nothing else.",
            pseudocode="not present -> return False\nremove from order, append to "
                       "order, return True",
            failures=["Updating `order` and forgetting that `values` must still hold "
                      "the same keys",
                      "Inserting the key on a miss, which silently turns a lookup "
                      "into a write",
                      "Rewriting `get` to touch as well — the docstring says reads "
                      "do not keep an entry alive, and something depends on that"],
            tags=["add-feature", "invariants"]),

        extend_class(
            "pt-class-apply", "All Of Them Or None Of Them",
            "`ConfigStore` records every write so support can answer 'when did this "
            "change'. It needs a batch write: `apply(updates)`.\n\n"
            "- Every key must be a string. If any key is not, NOTHING is written, "
            "nothing is logged, and the call returns False.\n"
            "- Otherwise the keys are set in sorted order — so the change log comes "
            "out identical on every machine — and the call returns True.\n"
            "- Each key set this way is logged exactly as `set` logs it, because "
            "`apply` should call `set` rather than reimplement it.\n\n"
            "Validating the whole batch before writing any of it is the entire "
            "problem. Half-applied configuration is worse than rejected "
            "configuration, and you cannot discover the bad key halfway through a "
            "sort — `sorted()` on mixed key types raises, and by then you have "
            "already written some of them.",
            "ConfigStore", _RefConfigStore, STORE_AFTER, STORE_BEFORE,
            [("a clean batch",
              ["__init__", "apply", "get", "get", "history"],
              [[{"retries": 3}], [{"timeout": 5, "retries": 1}], ["timeout"],
               ["retries"], ["retries"]]),
             ("a batch with a bad key changes nothing",
              ["__init__", "set", "apply", "get", "history"],
              [[], ["a", 1], [{"a": 9, "7": "x"}], ["a"], ["a"]])],
            [("existing behaviour untouched",
              ["__init__", "set", "set", "history", "get"],
              [[], ["a", 1], ["a", 2], ["a"], ["a"]]),
             ("empty batch is a successful batch",
              ["__init__", "apply", "history"], [[], [{}], ["a"]]),
             ("defaults are visible but not logged",
              ["__init__", "get", "history", "apply", "history"],
              [[{"a": 1}], ["a"], ["a"], [{"a": 2}], ["a"]]),
             ("None is a value, not an absence",
              ["__init__", "apply", "get"], [[], [{"a": None}], ["a"]])],
            edges=[("batch of one", ["__init__", "apply", "get"],
                    [[], [{"z": 1}], ["z"]]),
                   ("unknown key still reads as the default",
                    ["__init__", "apply", "get"], [[], [{"a": 1}], ["nope"]])],
            difficulty="MEDIUM", family="codebase_class",
            nudge="Two passes. The first one only asks questions; the second one is "
                  "the only one allowed to write.",
            pseudocode="if any key is not a str: return False\n"
                       "for key in sorted(updates): self.set(key, updates[key])\n"
                       "return True",
            failures=["Setting as you validate, so the first bad key leaves the "
                      "earlier ones already written and logged",
                      "Iterating `updates` in its own order, which is insertion "
                      "order and differs between callers",
                      "Writing `self.values[key] = value` directly and skipping the "
                      "change log the whole class exists for"],
            tags=["add-feature", "atomicity"]),
    ]


# ---------------------------------------------------------------------------
# 12. Refactor safely
# ---------------------------------------------------------------------------
#
# A refactor with no new requirement grades as a free clear: the code already
# passes, so submitting it untouched wins. Each of these therefore carries a new
# requirement that the existing shape makes painful — a fourth field, a fifth
# unit — so the tests genuinely fail until the duplication is gone. That is also
# the honest version of the task: nobody refactors for its own sake, they
# refactor because the next change was going to hurt.

CHECK_BEFORE = '''
"""importer.py — the complaints we make about an uploaded row."""


def check_row(row):
    """Return a list of complaints about one import row, in field order."""
    problems = []

    name = row.get("name")
    if name is None or str(name).strip() == "":
        problems.append("name is missing")

    email = row.get("email")
    if email is None or str(email).strip() == "":
        problems.append("email is missing")

    region = row.get("region")
    if region is None or str(region).strip() == "":
        problems.append("region is missing")

    return problems
'''

CHECK_AFTER = '''
"""importer.py — the complaints we make about an uploaded row."""

REQUIRED = ("name", "email", "region", "team")


def check_row(row):
    """Return a list of complaints about one import row, in field order."""
    problems = []
    for field in REQUIRED:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            problems.append(f"{field} is missing")
    return problems
'''

RENDER_BEFORE = '''
"""status_page.py — turning numbers into the strings humans read."""


def render(value, kind):
    """Format one metric for the status page."""
    if kind == "bytes":
        return str(round(value / 1024, 1)) + " KiB"
    if kind == "ms":
        return str(round(value / 1000, 2)) + " s"
    if kind == "count":
        return str(int(value))
    return str(value)
'''

RENDER_AFTER = '''
"""status_page.py — turning numbers into the strings humans read."""

# kind -> (divisor, decimal places, suffix). Adding a unit is now a line of
# data rather than a branch, which is the whole reason this is a table.
SCALED = {
    "bytes": (1024, 1, " KiB"),
    "ms": (1000, 2, " s"),
    "percent": (1, 1, "%"),
}


def render(value, kind):
    """Format one metric for the status page."""
    if kind in SCALED:
        divisor, places, suffix = SCALED[kind]
        return str(round(value / divisor, places)) + suffix
    if kind == "count":
        return str(int(value))
    return str(value)
'''


def _ref_numbered(lines):
    return ["%d: %s" % (i + 1, line) for i, line in enumerate(lines)]


def _ref_check_row(row):
    complaints = []
    for field in ("name", "email", "region", "team"):
        value = row.get(field)
        if value is None or not str(value).strip():
            complaints.append(field + " is missing")
    return complaints


def _ref_render_metric(value, kind):
    table = {"bytes": (1024, 1, " KiB"), "ms": (1000, 2, " s"),
             "percent": (1, 1, "%")}
    if kind in table:
        divisor, places, suffix = table[kind]
        return "%s%s" % (round(value / divisor, places), suffix)
    if kind == "count":
        return "%d" % int(value)
    return str(value)


def refactorwork() -> list:
    return [
        guided(
            "pt-refactor-enumerate", "The Index You Were Keeping By Hand",
            "This is the code as it stands:\n\n"
            "```python\n"
            "def numbered(lines):\n"
            "    out = []\n"
            "    number = 1\n"
            "    for line in lines:\n"
            "        out.append(str(number) + \": \" + line)\n"
            "        number = number + 1\n"
            "    return out\n"
            "```\n\n"
            "It works. It also carries a counter that can be incremented in the "
            "wrong branch, forgotten in a `continue`, or reset by accident — three "
            "bugs that cannot exist in the version below.\n\n"
            "Fill in the missing expression. The behaviour must not change: "
            "numbering starts at 1.",
            "numbered", "lines", _ref_numbered,
            """
            def numbered(lines):
                \"\"\"Prefix each line with its 1-based number: '1: first'.\"\"\"
                out = []
                for number, line in enumerate(lines, 1):
                    out.append(f"{number}: {line}")
                return out
            """,
            [("enumerate(lines, 1)",
              "walk the lines together with their 1-based numbers")],
            [("three lines", [["first", "second", "third"]]),
             ("one line", [["only"]])],
            [("blank line still numbered", [["a", "", "b"]]),
             ("numbering starts at one", [["x"]]),
             ("ten lines", [[str(i) for i in range(10)]])],
            edges=[("no lines", [[]])],
            pattern="ARRAY", family="codebase_refactor", realm="coding_coliseum",
            scaffold_for="ENUMERATE, INSTEAD OF A COUNTER",
            failures=["`enumerate(lines)` starts at 0, which renumbers every line",
                      "`enumerate(lines, start=1)` is the same thing spelled longer"],
            tags=["refactor"]),

        work("pt-refactor-required", "The Fourth Copy Of The Same Check",
             "`importer.py` checks three fields with three copies of the same five "
             "lines. Product wants a fourth field, `team`, checked the same way and "
             "complained about in the same format.\n\n"
             "You could paste the block a fourth time. Do not. Replace the three "
             "copies with one loop over a list of required field names, then add "
             "`team` to that list.\n\n"
             "The complaints keep their exact wording — `\"name is missing\"` — and "
             "their order: name, email, region, team. A field is missing when it is "
             "absent, None, or nothing but whitespace." + GIVEN_NOTE,
             "check_row", "row", _ref_check_row, CHECK_AFTER,
             [("everything present", [{"name": "Ada", "email": "a@b.c",
                                       "region": "north", "team": "core"}]),
              ("the new field is missing", [{"name": "Ada", "email": "a@b.c",
                                             "region": "north"}])],
             [("one missing", [{"name": "", "email": "a@b.c", "region": "n",
                                "team": "core"}]),
              ("whitespace is missing", [{"name": "   ", "email": "a@b.c",
                                          "region": "n", "team": "core"}]),
              ("None is missing", [{"name": None, "email": "a@b.c", "region": "n",
                                    "team": "core"}]),
              ("order is fixed", [{"team": "core", "region": "n"}]),
              ("a number is present", [{"name": 0, "email": "a@b.c", "region": "n",
                                        "team": "core"}])],
             edges=[("empty row", [{}]),
                    ("unknown fields ignored", [{"name": "A", "email": "e",
                                                 "region": "r", "team": "t",
                                                 "extra": "ignored"}])],
             difficulty="TUTORIAL", pattern="ARRAY", family="codebase_refactor",
             realm="coding_coliseum", starter_code=CHECK_BEFORE,
             encounter="REFACTOR_QUEST", secondary=["STRING"],
             nudge="The three blocks differ in exactly one thing: the field name. "
                   "That is the thing that becomes the loop variable.",
             pseudocode="REQUIRED = (...)\nfor field in REQUIRED: complain if absent, "
                        "None, or blank",
             failures=["Pasting the block a fourth time, which passes the tests and "
                       "guarantees a fifth copy exists by Christmas",
                       "`if not row.get(field)` also rejects `0` and `False`, which "
                       "are present values",
                       "Iterating a set instead of a tuple, so the complaint order "
                       "changes between runs"],
             tags=["refactor", "given-codebase"]),

        work("pt-refactor-units", "A Branch Per Unit, Forever",
             "`status_page.py` formats metrics with one `if` per unit. A fifth is "
             "wanted — `percent`, one decimal place, a `%` suffix, no division — "
             "and the branches have started to look like data pretending to be "
             "code.\n\n"
             "Replace the scaled branches with a table from kind to "
             "`(divisor, decimal places, suffix)` and look the kind up. The "
             "existing output must not change by one character:\n\n"
             "- `bytes`: divide by 1024, round to 1, suffix `\" KiB\"`\n"
             "- `ms`: divide by 1000, round to 2, suffix `\" s\"`\n"
             "- `percent`: no division, round to 1, suffix `\"%\"`\n"
             "- `count`: `str(int(value))`, no suffix — it does not fit the table "
             "and should not be forced into it\n"
             "- anything else: `str(value)`" + GIVEN_NOTE,
             "render", "value, kind", _ref_render_metric, RENDER_AFTER,
             [("bytes", [2048, "bytes"]), ("the new unit", [99.456, "percent"])],
             [("milliseconds", [1500, "ms"]),
              ("count truncates", [7.9, "count"]),
              ("unknown kind", [7.5, "widgets"]),
              ("rounding to one place", [1536, "bytes"]),
              ("zero", [0, "bytes"]),
              ("percent over a hundred", [131.25, "percent"])],
             edges=[("negative", [-2048, "bytes"]),
                    ("unknown kind of a string value", ["n/a", "widgets"])],
             difficulty="EASY", pattern="HASH_MAP", family="codebase_refactor",
             realm="coding_coliseum", starter_code=RENDER_BEFORE,
             encounter="REFACTOR_QUEST", time="O(1)", space="O(1)",
             nudge="Write down what the three scaled branches have in common: a "
                   "divisor, a number of places, a suffix. That tuple is the table "
                   "row.",
             pseudocode="SCALED = {kind: (divisor, places, suffix)}\n"
                        "kind in SCALED -> round(value / divisor, places) + suffix\n"
                        "count -> str(int(value))\notherwise -> str(value)",
             failures=["Forcing `count` into the table with a divisor of 1, which "
                       "renders `7` as `7.0` and changes existing output",
                       "Adding a fourth `if` and calling it done",
                       "Dropping the `str()` around the rounded number, so the "
                       "suffix concatenation raises TypeError"],
             tags=["refactor", "given-codebase"]),
    ]


# ---------------------------------------------------------------------------

def build() -> list:
    problems = (logs() + csvwork() + jsonwork() + configwork() + regexwork()
                + textwork() + timework() + filework() + featurework()
                + bugwork() + classwork() + refactorwork())

    # A duplicated id silently shadows a problem in the corpus index, so it is
    # cheaper to notice it here than to wonder later why one never appears.
    seen = set()
    for problem in problems:
        if problem.id in seen:
            raise ValueError(f"duplicate problem id {problem.id!r}")
        seen.add(problem.id)
    return problems
