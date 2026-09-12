"""Mini-Repo Battles: somebody else's codebase, a timer, and a test suite.

Every other encounter in this game hands the player one function and a blank
body. That is not what the practical test looks like and it is not what work
looks like. Work is three to eight files written by somebody who has left the
company, a suite that mostly passes, and a ticket that says one thing while the
code says another. This module is the repositories and the rules of that fight.

WHAT A MINI-REPO IS

  A `Repo` is a frozen record of three things: the project (`files`), the
  graded suite (`tests`), and a reference patch that provably solves it
  (`patch`). Nothing in it is generated at runtime, so a repo the player saw
  yesterday is the same repo today, down to the whitespace.

  Execution is `sandbox.run_project`, unchanged and unrouted-around. The
  project is a dict of {relative path: source}, the suite is a list of test
  file paths, and `sandbox.write_project` is the thing that decides whether a
  filename is acceptable. This module never touches the filesystem.

THE CODE IS MEDIOCRE ON PURPOSE

  Not broken. Working code, written in a hurry by someone competent who had
  another three tickets open. A function that grew a second job and never got
  split. A name that was accurate three commits ago. A comment that is now a
  lie. A helper nobody deleted. A guard against an impossible input standing
  next to an unguarded real one. Two files that disagree about naming because
  two people wrote them.

  That is the whole point. The skill being trained here is READING, and you
  cannot train reading on clean code. Clean code is not read; it is skimmed.

THREE TASK SHAPES

  ADD_FEATURE       a test file arrives that fails; make it pass.
  FIX_BUG           an existing test fails; find the cause, not the symptom.
  PRESERVE_CONTRACT the obvious fix breaks a caller elsewhere in the repo, and
                    an existing test catches it. Most repos carry this one,
                    because it is the shape that teaches the most: it is the
                    difference between changing code and changing a system.

GRADING IS THE SUITE, AND IT IS HONEST

  Three conditions, all of them required:
    * every target test passes (it failed before the player touched anything),
    * every other test still passes — a regression fails the encounter,
    * the test files are exactly the ones that were handed out.

  That last one is structural rather than moral. `assemble()` lays the player's
  files down first and then overwrites the test paths with the pristine bodies,
  so a submission that edits or deletes a test simply does not get to. The
  tamper check exists on top of that to say so out loud and fail the attempt,
  because silently ignoring a cheat teaches the player that it half-worked.

PROVABLY WINNABLE

  `audit()` runs every repo twice: once as handed out, where the targets must
  fail and everything else must pass, and once with the reference patch
  applied, where the whole suite must go green. A Mini-Repo nobody can beat is
  worse than no Mini-Repo, and the only way to know is to beat it.

WHAT THIS MODULE DOES NOT DO

  It does not decide who may fight, what it is worth, or what is shown. It is
  handed a mode and a set of sealed capabilities and it redacts accordingly;
  the question of what is sealed is `finalexam.sealed(encounter, capability)`
  at the engine's call site, which remains the one way to ask. See CONTRACT at
  the bottom of this file for the six functions the engine needs.
"""
from __future__ import annotations

import ast
import hashlib
import random
import sys
from dataclasses import dataclass, field
from typing import Iterable

from . import config, grading, sandbox

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

ENCOUNTER_KIND = "MINI_REPO"

TASK_SHAPES = ("ADD_FEATURE", "FIX_BUG", "PRESERVE_CONTRACT")

SHAPE_BLURB = {
    "ADD_FEATURE": "A test arrived that has never passed. Make it pass.",
    "FIX_BUG": "A test that used to pass does not. Find the cause, not the symptom.",
    "PRESERVE_CONTRACT": "Something else in here depends on what you are about to "
                         "change. The suite knows what.",
}

# Outcomes, worst to best. `grade` returns exactly one.
OUTCOMES = (
    "TAMPERED",     # the suite was edited or deleted; the attempt is void
    "BROKEN",       # the project no longer imports, or a test file blew up
    "REGRESSED",    # the target passes but something that used to pass does not
    "INCOMPLETE",   # no regression, but a target test still fails
    "SOLVED",       # every test green
)

OUTCOME_BLURB = {
    "TAMPERED": "You changed the tests. The tests are the only honest thing in "
                "the room, so that is the end of the attempt.",
    "BROKEN": "The project does not run any more. Import it before you judge it.",
    "REGRESSED": "You made the new test pass by breaking an old one. That is a "
                 "trade the repository did not agree to.",
    "INCOMPLETE": "Nothing is broken that was not broken before. The job is "
                  "still not done.",
    "SOLVED": "Green, all of it, including the parts you did not write.",
}

# How long a repo of each size is honestly worth. Read time dominates: a player
# who can write the fix in ninety seconds still has to find where it goes.
DIFFICULTY_SECONDS = {
    "EASY": 600, "MEDIUM": 900, "HARD": 1500, "ELITE": 1800, "BOSS": 2100,
}


def src(text: str) -> str:
    """File bodies are written flush-left inside raw triple-quoted literals.

    Raw, because a repo that greps for "\\n" must still contain a backslash and
    an n when it lands on disk rather than a newline the outer literal ate.
    """
    return text.strip("\n") + "\n"


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fix:
    """One edit from the reference patch.

    An exact-text replacement rather than a whole replacement file, for two
    reasons: it stays honest about how small the real change is, and `old`
    failing to appear exactly once is a loud signal that the repo body drifted
    away from the patch that is supposed to solve it. `old == ""` creates a new
    file, which is legitimate for a feature that wants a module of its own.
    """
    path: str
    old: str
    new: str
    why: str = ""


@dataclass(frozen=True)
class Repo:
    id: str
    title: str
    difficulty: str
    shapes: tuple
    brief: str                 # the ticket, as the player receives it
    start_file: str            # where to start reading; withheld in Interview Mode
    start_note: str            # why there; also withheld
    files: dict                # editable project sources and fixtures
    tests: dict                # the graded suite. Never editable. Ever.
    targets: tuple             # test ids that must go red -> green
    patch: tuple               # Fix, ... — the proof it can be won
    realm: str = "debugging_dungeon"
    tags: tuple = ()
    target_seconds: int = 0
    lesson: str = ""           # the one sentence, shown only in the debrief

    # -- derived ------------------------------------------------------------
    @property
    def test_paths(self) -> list:
        return sorted(self.tests)

    @property
    def clock(self) -> int:
        return self.target_seconds or DIFFICULTY_SECONDS.get(self.difficulty, 900)

    @property
    def file_count(self) -> int:
        return len(self.files) + len(self.tests)

    @property
    def byte_count(self) -> int:
        return sum(len(v) for v in self.files.values()) + \
               sum(len(v) for v in self.tests.values())

    def test_digest(self) -> dict:
        """sha256 per test file. The tamper check compares against this."""
        return {p: hashlib.sha256(b.encode("utf-8")).hexdigest()
                for p, b in self.tests.items()}


# ---------------------------------------------------------------------------
# Assembly, which is where the cheat is made impossible
# ---------------------------------------------------------------------------

# Anything the player sends under one of these paths is discarded before it can
# reach the sandbox. A test directory is reserved wholesale rather than by file,
# so that "tests/test_ledger.py.bak" and friends cannot shadow a real suite.
_RESERVED: dict = {}


def _reserved_prefixes(repo: Repo) -> tuple:
    if repo.id not in _RESERVED:
        out = set()
        for path in repo.tests:
            head = path.split("/")[0]
            out.add(head + "/" if "/" in path else path)
        _RESERVED[repo.id] = tuple(sorted(out))
    return _RESERVED[repo.id]


def _is_reserved(repo: Repo, path: str) -> bool:
    if path in repo.tests:
        return True
    return any(path.startswith(p) for p in _reserved_prefixes(repo) if p.endswith("/"))


def assemble(repo: Repo, submitted: dict | None = None) -> dict:
    """The file set that actually runs.

    Order is the whole of the security model here. The pristine project goes
    down first, the player's edits go on top of it, and then the test files go
    on top of everything — from `repo.tests`, never from the submission. A
    player cannot weaken a test because the bytes they sent for it are not the
    bytes that get written.
    """
    files = dict(repo.files)
    for path, body in (submitted or {}).items():
        if not isinstance(path, str) or not isinstance(body, str):
            continue
        if _is_reserved(repo, path):
            continue      # handled by check_tests; here it simply does not land
        files[path] = body
    files.update(repo.tests)
    return files


# ---------------------------------------------------------------------------
# The tamper check
# ---------------------------------------------------------------------------


@dataclass
class Tamper:
    edited: list = field(default_factory=list)
    deleted: list = field(default_factory=list)
    shadowed: list = field(default_factory=list)   # new files under a test path

    @property
    def clean(self) -> bool:
        return not (self.edited or self.deleted or self.shadowed)

    def message(self) -> str:
        if self.clean:
            return ""
        bits = []
        if self.edited:
            bits.append("edited " + ", ".join(sorted(self.edited)))
        if self.deleted:
            bits.append("deleted " + ", ".join(sorted(self.deleted)))
        if self.shadowed:
            bits.append("added " + ", ".join(sorted(self.shadowed)) +
                        " inside the test directory")
        return ("The suite is not the suite that was handed out: " +
                "; ".join(bits) + ".")

    def to_dict(self) -> dict:
        return {"clean": self.clean, "edited": sorted(self.edited),
                "deleted": sorted(self.deleted), "shadowed": sorted(self.shadowed),
                "message": self.message()}


def check_tests(repo: Repo, submitted: dict | None, *, full_tree: bool = True) -> Tamper:
    """Did the player edit, delete, or shadow a test file?

    `full_tree=True` means the submission is the player's whole working tree,
    which is what the editor sends, and therefore that a missing test file was
    deleted rather than merely untouched. A partial submission (one file saved
    from a tab) must pass `full_tree=False` or every unsent test reads as a
    deletion.
    """
    if submitted is None:
        # Nothing was sent, so nothing was tampered with. `grade(repo)` with no
        # submission means `run it as handed out`, not `the player deleted
        # everything`, and those must not produce the same verdict.
        return Tamper()
    tamper = Tamper()
    digests = repo.test_digest()
    for path, expected in digests.items():
        if path not in submitted:
            if full_tree:
                tamper.deleted.append(path)
            continue
        body = submitted[path]
        if not isinstance(body, str):
            tamper.edited.append(path)
            continue
        actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if actual != expected:
            tamper.edited.append(path)
    for path in submitted:
        if isinstance(path, str) and path not in digests and _is_reserved(repo, path):
            tamper.shadowed.append(path)
    return tamper


# ---------------------------------------------------------------------------
# Running and grading
# ---------------------------------------------------------------------------


@dataclass
class Verdict:
    repo_id: str
    outcome: str
    solved: bool
    targets: list = field(default_factory=list)      # [{id, status, message}]
    regressions: list = field(default_factory=list)  # [{id, status, message}]
    tests: list = field(default_factory=list)        # every test, in suite order
    passed: int = 0
    total: int = 0
    tamper: dict = field(default_factory=dict)
    seconds: float | None = None
    in_time: bool | None = None
    message: str = ""
    stdout: str = ""
    stderr: str = ""
    error: dict | None = None
    wall_ms: float = 0.0
    hardened: bool = True

    def to_dict(self) -> dict:
        return {
            "repo_id": self.repo_id, "outcome": self.outcome, "solved": self.solved,
            "targets": self.targets, "regressions": self.regressions,
            "tests": self.tests, "passed": self.passed, "total": self.total,
            "tamper": self.tamper, "seconds": self.seconds, "in_time": self.in_time,
            "message": self.message, "stdout": self.stdout, "stderr": self.stderr,
            "error": self.error, "wall_ms": round(self.wall_ms, 2),
            "hardened": self.hardened,
        }


def run(repo: Repo, files: dict | None = None, *, timeout_ms: int | None = None,
        wall_seconds: int | None = None) -> sandbox.ExecutionReport:
    """Execute a file set against this repo's suite. No judgement, just facts.

    The wall and CPU budgets are widened, because the defaults are sized for
    one function against a dozen derived cases and a repo runs its whole suite
    — a dozen test functions across several modules, each with its own import.
    The per-test deadline is untouched: an individual test here is no more
    entitled to hang than any other.
    """
    return sandbox.run_project(
        files if files is not None else assemble(repo),
        repo.test_paths,
        timeout_ms=timeout_ms or config.PER_TEST_TIMEOUT_MS,
        wall_seconds=wall_seconds or max(config.SANDBOX_WALL_SECONDS, 20),
        cpu_seconds=max(config.SANDBOX_CPU_SECONDS, 10),
    )


def _classify(repo: Repo, report: sandbox.ExecutionReport) -> tuple:
    """Split the suite into targets and everything else."""
    targets, regressions, rows = [], [], []
    seen = set()
    for t in report.tests:
        row = {"id": t.name, "status": t.status, "message": t.message,
               "ms": round(t.ms, 2), "target": t.name in repo.targets}
        rows.append(row)
        seen.add(t.name)
        if t.name in repo.targets:
            targets.append(row)
        elif t.status != "pass":
            regressions.append(row)
    # A test that did not report at all is a test that was made to disappear —
    # by deleting the function, by breaking the import, by renaming the module.
    # Silence is a failure, not an absence of one.
    for name in repo.targets:
        if name not in seen:
            row = {"id": name, "status": "missing",
                   "message": "the test never ran", "ms": 0.0, "target": True}
            targets.append(row)
            rows.append(row)
    return targets, regressions, rows


def grade(repo: Repo, submitted: dict | None = None, *, seconds: float | None = None,
          full_tree: bool = True, timeout_ms: int | None = None) -> Verdict:
    """The whole encounter, decided.

    The submission is {path: source} for the project files the player edited.
    Test paths in it are checked and then thrown away; see `assemble`.
    """
    tamper = check_tests(repo, submitted, full_tree=full_tree)
    verdict = Verdict(repo_id=repo.id, outcome="TAMPERED", solved=False,
                      tamper=tamper.to_dict(), seconds=seconds)
    if seconds is not None:
        verdict.in_time = seconds <= repo.clock

    if not tamper.clean:
        # Deliberately no run. There is nothing to learn from the suite once we
        # know the player was willing to edit it, and running anyway would
        # produce a green wall next to a failure, which reads as a bug.
        verdict.message = tamper.message() + " " + OUTCOME_BLURB["TAMPERED"]
        return verdict

    report = run(repo, assemble(repo, submitted), timeout_ms=timeout_ms)
    verdict.stdout, verdict.stderr = report.stdout, report.stderr
    verdict.error, verdict.wall_ms = report.error, report.wall_ms
    verdict.hardened = report.hardened

    if not report.ok or not report.tests:
        verdict.outcome = "BROKEN"
        detail = (report.error or {}).get("message", "") if report.error else ""
        verdict.message = OUTCOME_BLURB["BROKEN"] + ((" " + detail) if detail else "")
        return verdict

    targets, regressions, rows = _classify(repo, report)
    verdict.targets, verdict.regressions, verdict.tests = targets, regressions, rows
    verdict.passed = report.passed_count
    verdict.total = len(rows)
    targets_green = all(r["status"] == "pass" for r in targets) and bool(targets)

    if regressions:
        # Regressed whether or not the targets went green. BROKEN is reserved
        # for a project that did not run at all; saying it here would print
        # `the project does not run any more` next to a suite that plainly did.
        verdict.outcome = "REGRESSED"
    elif targets_green:
        verdict.outcome, verdict.solved = "SOLVED", True
    else:
        verdict.outcome = "INCOMPLETE"
    verdict.message = OUTCOME_BLURB[verdict.outcome]
    return verdict


def rank_for(repo: Repo, verdict: Verdict, *, seconds: float,
             hints_used: int = 0, first_try: bool = True) -> str:
    """Same ladder as every other encounter; the clock is the repo's own."""
    return grading.rank_for(
        solved=verdict.solved, hints_used=hints_used, seconds=seconds,
        target_seconds=repo.clock, used_phoenix=False, first_try=first_try)


# ---------------------------------------------------------------------------
# The reference patch
# ---------------------------------------------------------------------------


def apply_patch(repo: Repo, fixes: Iterable[Fix] | None = None) -> dict:
    """The repo as the reference solution leaves it.

    Raises if an anchor is missing or ambiguous, which is the point: a patch
    that no longer applies is a repo that can no longer be proven winnable, and
    `audit` would otherwise report that as a cheerful red suite.
    """
    files = dict(repo.files)
    for fix in (fixes if fixes is not None else repo.patch):
        if fix.old == "":
            if fix.path in files:
                raise ValueError("%s: patch would create %s, which exists"
                                 % (repo.id, fix.path))
            files[fix.path] = fix.new
            continue
        body = files.get(fix.path)
        if body is None:
            raise ValueError("%s: patch targets missing file %s" % (repo.id, fix.path))
        hits = body.count(fix.old)
        if hits != 1:
            raise ValueError("%s: anchor appears %d times in %s"
                             % (repo.id, hits, fix.path))
        files[fix.path] = body.replace(fix.old, fix.new)
    return files


def reference_files(repo: Repo) -> dict:
    """Project + suite, solved. Never travels to the client during a fight."""
    files = apply_patch(repo)
    files.update(repo.tests)
    return files


# ---------------------------------------------------------------------------
# What the player is allowed to see
# ---------------------------------------------------------------------------

# Capabilities this encounter consults. The engine resolves each one with
# `finalexam.sealed(encounter, cap)` and passes the set it got back; this module
# never decides for itself whether something is available, because a second
# place that answers that question is how the first one stops being true.
#
#   WEAKNESS_MAP  the starting-file pointer and the task shapes. Both are a
#                 tactical read of the repo: they say where the soft spot is.
#   PATTERN       the acceptance criteria — which tests are the targets.
#   SOLUTION      the reference patch, in the debrief, after it is scored.
SEALED_CAPABILITIES = ("WEAKNESS_MAP", "PATTERN", "SOLUTION")


def player_view(repo: Repo, *, mode: str = config.MODE_ADVENTURE,
                sealed: Iterable[str] = ()) -> dict:
    """The encounter payload. The patch is not in it under any conditions.

    Interview Mode gets the brief, the files, the suite and the clock — the
    same thing a real practical hands over. No pointer at the file to start in,
    no list of which tests are the targets, no label saying which of the three
    shapes this is. Finding that out is the exercise.
    """
    sealed = set(sealed)
    if mode == config.MODE_INTERVIEW:
        sealed |= set(SEALED_CAPABILITIES)
    view = {
        "id": repo.id,
        "title": repo.title,
        "difficulty": repo.difficulty,
        "encounter_kind": ENCOUNTER_KIND,
        "realm": repo.realm,
        "brief": repo.brief,
        "target_seconds": repo.clock,
        "files": [{"path": p, "body": b, "editable": True}
                  for p, b in sorted(repo.files.items())],
        "tests": [{"path": p, "body": b, "editable": False}
                  for p, b in sorted(repo.tests.items())],
        "test_paths": repo.test_paths,
        "file_count": repo.file_count,
        "rules": [
            "Every test that passes now must still pass when you hand it back.",
            "The test files are read-only. Editing or deleting one ends the attempt.",
            "Standard library only.",
        ],
    }
    if "WEAKNESS_MAP" in sealed:
        view["start_file"] = ""
        view["start_note"] = ""
        view["shapes"] = []
    else:
        view["start_file"] = repo.start_file
        view["start_note"] = repo.start_note
        view["shapes"] = [{"id": s, "blurb": SHAPE_BLURB[s]} for s in repo.shapes]
    view["targets"] = [] if "PATTERN" in sealed else list(repo.targets)
    return view


def debrief(repo: Repo, verdict: Verdict, *, sealed: Iterable[str] = ()) -> dict:
    """What the player is owed afterwards.

    Learning never dead-ends, so this always says what the repo was about and
    which file the cause lived in — even on a tampered attempt, where the
    lesson is a different one. The reference patch itself is the worked
    solution and follows the same rule worked solutions follow everywhere else:
    after the attempt is scored, and not when SOLUTION is sealed.
    """
    sealed = set(sealed)
    out = {
        "repo_id": repo.id,
        "outcome": verdict.outcome,
        "headline": OUTCOME_BLURB.get(verdict.outcome, ""),
        "lesson": repo.lesson,
        "shapes": [{"id": s, "blurb": SHAPE_BLURB[s]} for s in repo.shapes],
        "where": repo.start_file,
        "regressions": [r["id"] for r in verdict.regressions],
        "targets": [{"id": r["id"], "status": r["status"]} for r in verdict.targets],
        "solution": [],
    }
    if "SOLUTION" not in sealed:
        out["solution"] = [
            {"path": f.path, "old": f.old, "new": f.new, "why": f.why}
            for f in repo.patch
        ]
    return out


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------

REPOS: dict = {}


def register(repo: Repo) -> Repo:
    if repo.id in REPOS:
        raise ValueError("duplicate mini-repo id: %s" % repo.id)
    REPOS[repo.id] = repo
    return repo


def get(repo_id: str) -> Repo | None:
    return REPOS.get(repo_id)


def catalogue(*, difficulty: str = "", tag: str = "") -> list:
    """Index cards, cheap enough to render a whole board from."""
    out = []
    for repo in REPOS.values():
        if difficulty and repo.difficulty != difficulty:
            continue
        if tag and tag not in repo.tags:
            continue
        out.append({
            "id": repo.id, "title": repo.title, "difficulty": repo.difficulty,
            "shapes": list(repo.shapes), "files": repo.file_count,
            "target_seconds": repo.clock, "realm": repo.realm,
            "tags": list(repo.tags),
        })
    out.sort(key=lambda c: (_tier(c["difficulty"]), c["id"]))
    return out


DIFFICULTY_ORDER = ["EASY", "MEDIUM", "HARD", "ELITE", "BOSS"]


def _tier(difficulty: str) -> int:
    """Position on the ladder. An unknown tier sorts to the top rather than
    raising, because a catalogue that cannot render is worse than one in an
    odd order."""
    try:
        return DIFFICULTY_ORDER.index(difficulty)
    except ValueError:
        return 0


def pick(*, difficulty: str = "", exclude: Iterable[str] = (), seed=None) -> Repo | None:
    """One repo, deterministically if a seed is given.

    Falls back through neighbouring difficulties rather than returning nothing:
    a board that offers no fight because the exact tier was exhausted is a dead
    end, and this game does not have those.
    """
    exclude = set(exclude)
    if difficulty:
        wanted = _tier(difficulty)
        tiers = sorted(DIFFICULTY_ORDER, key=lambda d: abs(_tier(d) - wanted))
    else:
        tiers = list(DIFFICULTY_ORDER)
    rng = random.Random(seed)
    for tier in tiers:
        pool = [r for r in REPOS.values()
                if r.difficulty == tier and r.id not in exclude]
        if pool:
            return rng.choice(sorted(pool, key=lambda r: r.id))
    pool = [r for r in REPOS.values() if r.id not in exclude]
    return rng.choice(sorted(pool, key=lambda r: r.id)) if pool else None


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------

_STDLIB = set(sys.stdlib_module_names)


def _imports(body: str) -> set:
    """Top-level module names imported by one file, or {"<syntax>"} if it will
    not even parse — which is worth knowing before a player is asked to read it."""
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return {"<syntax>"}
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # relative import, resolves inside the project
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _own_modules(repo: Repo) -> set:
    out = set()
    for path in list(repo.files) + list(repo.tests):
        if not path.endswith(".py"):
            continue
        parts = path.split("/")
        out.add(parts[0][:-3] if len(parts) == 1 else parts[0])
    return out


def static_audit(repo: Repo) -> dict:
    """Everything that can be checked without running anything."""
    own = _own_modules(repo)
    foreign, unparseable = set(), []
    bodies = dict(repo.files)
    bodies.update(repo.tests)
    for path, body in bodies.items():
        if not path.endswith(".py"):
            continue
        found = _imports(body)
        if "<syntax>" in found:
            unparseable.append(path)
            found.discard("<syntax>")
        foreign |= {n for n in found if n not in _STDLIB and n not in own}
    # The patched form has to be stdlib-clean too, or the worked solution
    # teaches a dependency the sandbox will refuse.
    try:
        patched = apply_patch(repo)
        patch_applies = True
        for path, body in patched.items():
            if path.endswith(".py"):
                foreign |= {n for n in _imports(body)
                            if n not in _STDLIB and n not in own and n != "<syntax>"}
    except ValueError:
        patch_applies = False

    return {
        "files": repo.file_count,
        "bytes": repo.byte_count,
        "within_file_limit": repo.file_count <= sandbox.MAX_PROJECT_FILES,
        "within_byte_limit": repo.byte_count <= sandbox.MAX_PROJECT_BYTES,
        # "3-8 files" is the brief, and it is a real constraint rather than a
        # decoration: a repo you cannot hold in your head in the first minute is
        # measuring stamina instead of reading.
        "size_ok": 3 <= repo.file_count <= 8,
        "source_files": len(repo.files),
        "test_files": len(repo.tests),
        "stdlib_only": not foreign,
        "foreign_imports": sorted(foreign),
        "parses": not unparseable,
        "unparseable": sorted(unparseable),
        "patch_applies": patch_applies,
        "start_file_exists": repo.start_file in repo.files,
        "has_targets": bool(repo.targets),
        "shapes_known": all(s in TASK_SHAPES for s in repo.shapes),
    }


def audit(repo: Repo) -> dict:
    """Run the repo as handed out, then run it solved. Both must hold.

    Before: every target red, everything else green. A target that already
    passes is not a task; a pre-existing failure that is not a target is a repo
    that cannot be finished.

    After: all green. This is the winnability proof, and it is the reason this
    function runs the sandbox instead of reasoning about the code.
    """
    out = {"id": repo.id, "title": repo.title, "difficulty": repo.difficulty}
    out.update(static_audit(repo))

    before = run(repo)
    out["before_ok"] = before.ok
    before_names = {t.name: t.status for t in before.tests}
    out["before_total"] = len(before.tests)
    missing = [t for t in repo.targets if t not in before_names]
    out["targets_exist"] = not missing
    out["targets_missing"] = missing
    out["targets_fail_before"] = bool(repo.targets) and not missing and all(
        before_names[t] != "pass" for t in repo.targets)
    stray = sorted(n for n, s in before_names.items()
                   if s != "pass" and n not in repo.targets)
    out["others_pass_before"] = not stray
    out["stray_failures"] = stray
    if not before.ok:
        out["before_error"] = before.error

    if out["patch_applies"]:
        after = run(repo, reference_files(repo))
        after_names = {t.name: t.status for t in after.tests}
        out["after_ok"] = after.ok
        out["after_total"] = len(after.tests)
        failed_after = sorted(n for n, s in after_names.items() if s != "pass")
        out["patch_solves"] = after.ok and bool(after.tests) and not failed_after
        out["after_failures"] = failed_after
        if not after.ok:
            out["after_error"] = after.error
    else:
        out["after_ok"] = False
        out["patch_solves"] = False
        out["after_failures"] = ["patch did not apply"]

    # The cheat, attempted, twice: edit a test and delete a test. Both must be
    # caught, and neither may be allowed to change what the suite reports.
    a_test = repo.test_paths[0]
    full = dict(repo.files)
    full.update(repo.tests)
    edited = dict(full)
    edited[a_test] = "def test_free_pass():\n    assert True\n"
    deleted = {k: v for k, v in full.items() if k != a_test}
    v_edit = grade(repo, edited)
    v_delete = grade(repo, deleted)
    out["edit_detected"] = v_edit.outcome == "TAMPERED"
    out["delete_detected"] = v_delete.outcome == "TAMPERED"
    # Belt and braces: even if the check were removed, the bytes must not land.
    out["suite_immutable"] = assemble(repo, edited)[a_test] == repo.tests[a_test]

    out["ok"] = all([
        out["within_file_limit"], out["within_byte_limit"], out["stdlib_only"],
        out["parses"], out["patch_applies"], out["start_file_exists"],
        out["has_targets"], out["shapes_known"], out["targets_exist"], out["size_ok"],
        out["targets_fail_before"], out["others_pass_before"], out["patch_solves"],
        out["edit_detected"], out["delete_detected"], out["suite_immutable"],
    ])
    return out


def self_check(ids: Iterable[str] = ()) -> dict:
    """Every repo, audited. Called by the acceptance tests and by hand."""
    wanted = list(ids) or list(REPOS)
    rows = [audit(REPOS[i]) for i in wanted]
    return {
        "repos": len(rows),
        "ok": all(r["ok"] for r in rows),
        "failed": [r["id"] for r in rows if not r["ok"]],
        "rows": rows,
    }


# ===========================================================================
# The repositories
# ===========================================================================
#
# House style for everything below this line: the code is WORKING and it is
# MEDIOCRE. Those are not in tension. Every file here would pass a distracted
# review on a Thursday afternoon, which is exactly how code like this gets into
# production and exactly why reading it is a trainable skill. Specifically, in
# every repo, at least three of:
#
#   * a function that does two things because the second one was added later,
#   * a name that was accurate three commits ago,
#   * a comment that is now a lie,
#   * a helper or an exception class nobody ever wired up,
#   * a guard against an input that cannot occur, beside an unguarded one that
#     occurs every day,
#   * two files that disagree about quoting and naming, because two people.
#
# What is NOT here: a deliberately confusing maze, dead code that misleads
# about the actual defect, or a joke. The player has a clock running.


# ---------------------------------------------------------------------------
# logsift — the ingest job everybody has written twice
# ---------------------------------------------------------------------------

_LOGSIFT_INIT = r'''
"""logsift: read the log, say what happened."""
from .parse import parse_line, parse_lines
from .summary import busiest_minute, level_counts

__all__ = ["parse_line", "parse_lines", "level_counts", "busiest_minute"]
'''

_LOGSIFT_PARSE = r'''
"""Line parsing for the ingest job.

The shipper emits `DATE TIME LEVEL MESSAGE`, space separated, and has done
since the rewrite. Everything downstream goes through parse_line, so this is
the only module in the package that knows what a log line looks like.
"""
import re

# Severity order, lowest first. summary.busiest_minute sorts on this.
LEVELS = ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]

_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)$")


def parse_line(raw):
    """Parse one line into a record.

    Returns None when the line is not a log line: a blank separator, a
    continuation line from a stack trace, a banner the deploy script printed.
    The caller decides what a None means, because it means different things in
    different places.
    """
    if raw is None:
        return None
    text = raw.rstrip("\n").rstrip()
    if not text:
        return None
    found = _LINE.match(text)
    if not found:
        return None
    date, clock, level, message = found.groups()
    return {"date": date, "time": clock, "level": level.upper(),
            "message": message}


def parse_lines(lines, level=None):
    """Parse an iterable of lines, and filter by level if one was named.

    Two jobs in one function. The filter arrived the week before the demo and
    nobody has been back since.
    """
    out = []
    for raw in lines:
        record = parse_line(raw)
        if record is None:
            continue
        if level is not None and record["level"] != level.upper():
            continue
        out.append(record)
    return out


def _shorten(message, width=60):
    # For the CLI table. The CLI was retired in March.
    if len(message) <= width:
        return message
    return message[:width - 1] + "..."
'''

_LOGSIFT_SUMMARY = r'''
"""Rollups over log lines.

Note for whoever picks this up: parse.parse_line is the only thing that knows
the wire format, and it should stay that way. Everything here goes through it.
"""
from collections import Counter

from .parse import parse_line


def level_counts(lines):
    """Count records per level. Lines that are not records are skipped."""
    counts = Counter()
    for raw in lines:
        record = parse_line(raw)
        if record is None:
            continue
        counts[record['level']] += 1
    return dict(counts)


def busiest_minute(lines):
    """The HH:MM that produced the most records. Ties go to the earliest.

    Returns an empty string when there is nothing to count, which the dashboard
    renders as a dash.
    """
    per_minute = {}
    for record in [r for r in (parse_line(l) for l in lines) if r]:
        minute = record['time'][:5]
        per_minute.setdefault(minute, 0)
        per_minute[minute] += 1
    if not per_minute:
        return ''
    best, best_count = '', -1
    for minute in sorted(per_minute):
        if per_minute[minute] > best_count:
            best, best_count = minute, per_minute[minute]
    return best
'''

_LOGSIFT_TEST_PARSE = r'''
"""Parser tests. These cover behaviour that other services already rely on."""
from logsift import parse


def test_parses_an_ordinary_line():
    record = parse.parse_line("2024-05-01 09:00:00 INFO server started")
    assert record["date"] == "2024-05-01"
    assert record["time"] == "09:00:00"
    assert record["level"] == "INFO"
    assert record["message"] == "server started"


def test_level_is_upper_cased():
    record = parse.parse_line("2024-05-01 09:00:01 warn disk at 91%")
    assert record["level"] == "WARN"


def test_a_line_that_is_not_a_record_is_None():
    # parse_line has exactly one way of saying "not a log line", and three
    # callers depend on it staying None. Blank, whitespace and prose all agree.
    assert parse.parse_line("") is None
    assert parse.parse_line("   ") is None
    assert parse.parse_line("Traceback (most recent call last):") is None


def test_parse_lines_filters_by_level_case_insensitively():
    lines = [
        "2024-05-01 09:00:00 INFO server started",
        "2024-05-01 09:00:01 ERROR upstream refused",
        "2024-05-01 09:00:02 INFO retrying",
    ]
    picked = parse.parse_lines(lines, level="error")
    assert len(picked) == 1
    assert picked[0]["message"] == "upstream refused"
'''

_LOGSIFT_TEST_SUMMARY = r'''
"""Summary tests.

The last one is new. Support cannot tell the difference between a quiet hour
and an hour where the shipper was emitting garbage we silently dropped, and
they have asked, twice.
"""
from logsift import summary

QUIET = [
    "2024-05-01 09:00:00 INFO server started",
    "",
    "2024-05-01 09:00:30 INFO ready",
    "2024-05-01 09:01:00 WARN disk at 91%",
]


def test_level_counts_ignores_blank_lines():
    assert summary.level_counts(QUIET) == {"INFO": 2, "WARN": 1}


def test_busiest_minute_picks_the_busiest():
    assert summary.busiest_minute(QUIET) == "09:00"


def test_busiest_minute_breaks_ties_by_earliest():
    lines = [
        "2024-05-01 11:05:00 INFO a",
        "2024-05-01 09:02:00 INFO b",
    ]
    assert summary.busiest_minute(lines) == "09:02"


def test_busiest_minute_of_nothing_is_empty():
    assert summary.busiest_minute([]) == ""
    assert summary.busiest_minute(["", "   "]) == ""


def test_level_counts_reports_unparsed_lines():
    lines = [
        "2024-05-01 09:00:00 INFO started",
        "",
        "   ",
        "Traceback (most recent call last):",
        "  File \"app.py\", line 12, in handler",
        "2024-05-01 09:00:02 warn disk at 91%",
    ]
    counts = summary.level_counts(lines)
    assert counts == {"INFO": 1, "WARN": 1, "UNPARSED": 2}
'''

register(Repo(
    id="logsift",
    title="logsift: the lines nobody counted",
    difficulty="EASY",
    shapes=("ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="fields_of_syntax",
    tags=("parsing", "text"),
    target_seconds=600,
    brief=(
        "Support has asked twice. They cannot tell a quiet hour from an hour "
        "where the shipper was emitting rubbish that we dropped on the floor, "
        "and level_counts is where the dropping happens.\n\n"
        "Count the lines that are not log records under the key UNPARSED. A "
        "blank or whitespace-only line is a separator, not rubbish, and does "
        "not count. Everything the suite already asserts must still hold."
    ),
    start_file="logsift/summary.py",
    start_note=(
        "level_counts is four lines long and one of them is the one you want. "
        "Read parse_line before you touch anything, though: it is the only "
        "function in the package that knows what a log line is, and it has "
        "exactly one way of saying `that was not one`."
    ),
    lesson=(
        "parse_line collapses two different things — a blank separator and a "
        "corrupt line — into one None. Widening its return type would have "
        "been the obvious fix and it would have broken three callers. The "
        "distinction belongs to the caller that cares about it."
    ),
    files={
        "logsift/__init__.py": src(_LOGSIFT_INIT),
        "logsift/parse.py": src(_LOGSIFT_PARSE),
        "logsift/summary.py": src(_LOGSIFT_SUMMARY),
    },
    tests={
        "tests/test_parse.py": src(_LOGSIFT_TEST_PARSE),
        "tests/test_summary.py": src(_LOGSIFT_TEST_SUMMARY),
    },
    targets=("tests/test_summary.py::test_level_counts_reports_unparsed_lines",),
    patch=(
        Fix(
            path="logsift/summary.py",
            old="""        record = parse_line(raw)
        if record is None:
            continue
        counts[record['level']] += 1""",
            new="""        record = parse_line(raw)
        if record is None:
            # parse_line says None for a blank separator and for a line that
            # was meant to be a record and is not. Only the second is news.
            if raw is not None and raw.strip():
                counts['UNPARSED'] += 1
            continue
        counts[record['level']] += 1""",
            why=("The distinction lives here because this is the only caller "
                 "that needs it. parse_line keeps its contract: not a record "
                 "is None, and it stays None."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# ledger — append-only stock book, and the one movement allowed to be negative
# ---------------------------------------------------------------------------

_LEDGER_INIT = r'''
"""ledger: what the warehouse says it has."""
from .book import ADJUST, RECEIVE, RETURN, SHIP, InsufficientStock, Ledger

__all__ = ["Ledger", "InsufficientStock", "RECEIVE", "SHIP", "ADJUST", "RETURN"]
'''

_LEDGER_BOOK = r'''
"""The stock book.

Movements are appended and never edited or deleted. That rule is the outcome
of the April audit and it is not up for discussion.
"""

RECEIVE = "RECEIVE"
SHIP = "SHIP"
ADJUST = "ADJUST"
RETURN = "RETURN"

# What each kind contributes to the balance.
SIGNS = {RECEIVE: 1, SHIP: -1, ADJUST: 1, RETURN: 1}


class InsufficientStock(Exception):
    """Raised when a shipment asks for more than the shelf is holding."""

    def __init__(self, sku, wanted, available):
        super().__init__("%s: wanted %d, have %d" % (sku, wanted, available))
        self.sku = sku
        self.wanted = wanted
        self.available = available


class Ledger:
    """An append-only list of movements, plus the sums you can take off it."""

    def __init__(self):
        self.movements = []
        # Running balance per sku, kept current on every append.
        self._totals = {}

    def record(self, sku, kind, qty, note=""):
        """Append one movement and return it.

        An adjustment may be negative; nothing else may. That is the whole of
        the sign policy and reconciliation depends on it.
        """
        if kind not in SIGNS:
            raise ValueError("unknown movement kind: %r" % (kind,))
        if qty is None:
            raise ValueError("qty is required")
        if kind != ADJUST and qty < 0:
            raise ValueError("only an adjustment may be negative")
        entry = {"sku": sku, "kind": kind, "qty": qty, "note": note}
        self.movements.append(entry)
        return entry

    def balance(self, sku):
        """Quantity on hand, replayed from the movements."""
        total = 0
        for movement in self.movements:
            if movement["sku"] != sku:
                continue
            total += SIGNS[movement["kind"]] * movement["qty"]
        return total

    def quantity(self, sku):
        # The picking service still calls the old name.
        return self.balance(sku)

    def skus(self):
        return sorted({m["sku"] for m in self.movements})

    def history(self, sku):
        return [m for m in self.movements if m["sku"] == sku]
'''

_LEDGER_AUDIT = r'''
"""Reconciliation: what the book says against what the shelf holds.

A negative balance is a discrepancy, not an error. The book is allowed to be
wrong - being wrong is the entire reason anyone counts the shelf - and hiding
that by refusing the movement would lose the only evidence we get.
"""
from .book import ADJUST


def negative_skus(ledger):
    """Every sku the book thinks we owe the universe."""
    return [s for s in ledger.skus() if ledger.balance(s) < 0]


def reconcile(ledger, counted):
    """Compare the book against a physical count.

    `counted` is {sku: how many were on the shelf}. Returns one dict per
    disagreement, sorted by sku, with the signed delta needed to agree.
    """
    out = []
    for sku in sorted(set(ledger.skus()) | set(counted)):
        book = ledger.balance(sku)
        real = counted.get(sku, 0)
        if book != real:
            out.append({'sku': sku, 'book': book, 'counted': real,
                        'delta': real - book})
    return out


def apply_corrections(ledger, discrepancies):
    """Write every discrepancy back as an adjustment, so the book agrees.

    The deltas are signed and are negative more often than not, because the
    usual finding is that we have fewer than we thought.
    """
    for item in discrepancies:
        ledger.record(item['sku'], ADJUST, item['delta'], note='stocktake')
    return ledger


def summary_line(ledger, sku):
    # Left over from the daily email. The email is now generated by the
    # reporting service, from this same data, in a different format.
    return '%s: %d on hand across %d movements' % (
        sku, ledger.balance(sku), len(ledger.history(sku)))
'''

_LEDGER_TEST_BOOK = r'''
"""Book tests.

The last one is new, and it is the ticket: the picking service oversold a pallet
of SKU-1 on Friday because nothing in here said it could not.
"""
from ledger import ADJUST, RECEIVE, RETURN, SHIP, InsufficientStock, Ledger


def test_receive_then_ship():
    book = Ledger()
    book.record("SKU-1", RECEIVE, 10)
    book.record("SKU-1", SHIP, 4)
    assert book.balance("SKU-1") == 6


def test_returns_come_back_onto_the_shelf():
    book = Ledger()
    book.record("SKU-2", RECEIVE, 5)
    book.record("SKU-2", SHIP, 5)
    book.record("SKU-2", RETURN, 2)
    assert book.balance("SKU-2") == 2


def test_the_old_name_still_works():
    book = Ledger()
    book.record("SKU-3", RECEIVE, 7)
    assert book.quantity("SKU-3") == book.balance("SKU-3") == 7


def test_only_an_adjustment_may_be_negative():
    book = Ledger()
    for kind in (RECEIVE, SHIP, RETURN):
        try:
            book.record("SKU-4", kind, -1)
        except ValueError:
            pass
        else:
            raise AssertionError("%s accepted a negative quantity" % kind)
    book.record("SKU-4", ADJUST, -1)
    assert book.balance("SKU-4") == -1


def test_an_unknown_movement_is_refused():
    book = Ledger()
    try:
        book.record("SKU-5", "TELEPORT", 1)
    except ValueError:
        return
    raise AssertionError("TELEPORT is not a movement kind")


def test_shipping_more_than_we_hold_is_refused():
    book = Ledger()
    book.record("SKU-1", RECEIVE, 3)
    try:
        book.record("SKU-1", SHIP, 5)
    except InsufficientStock as exc:
        assert exc.sku == "SKU-1"
        assert exc.wanted == 5
        assert exc.available == 3
    else:
        raise AssertionError("shipping 5 when we hold 3 must be refused")
    # And the refusal leaves no trace: the book is append-only, so a movement
    # that was not allowed to happen must not be in it.
    assert book.balance("SKU-1") == 3
    assert len(book.movements) == 1
'''

_LEDGER_TEST_AUDIT = r'''
"""Reconciliation tests. Written by the person who ran the April audit."""
from ledger import ADJUST, RECEIVE, SHIP, Ledger
from ledger import audit


def _seeded():
    book = Ledger()
    book.record('SKU-1', RECEIVE, 10)
    book.record('SKU-1', SHIP, 4)
    book.record('SKU-2', RECEIVE, 3)
    return book


def test_reconcile_reports_only_disagreements():
    book = _seeded()
    found = audit.reconcile(book, {'SKU-1': 6, 'SKU-2': 1})
    assert len(found) == 1
    assert found[0] == {'sku': 'SKU-2', 'book': 3, 'counted': 1, 'delta': -2}


def test_reconcile_notices_a_sku_the_book_has_never_heard_of():
    book = _seeded()
    found = audit.reconcile(book, {'SKU-1': 6, 'SKU-2': 3, 'SKU-9': 2})
    assert [f['sku'] for f in found] == ['SKU-9']
    assert found[0]['delta'] == 2


def test_corrections_are_written_back_as_adjustments():
    book = _seeded()
    audit.apply_corrections(book, audit.reconcile(book, {'SKU-1': 6, 'SKU-2': 1}))
    assert book.balance('SKU-2') == 1
    assert book.movements[-1]['kind'] == ADJUST
    assert book.movements[-1]['note'] == 'stocktake'


def test_a_bad_count_is_allowed_to_drive_the_book_negative():
    # The shelf is the truth even when the truth is nonsense. A write-off that
    # was entered twice puts the book below zero, and negative_skus is how
    # anybody finds out. Refusing the adjustment would hide the evidence.
    book = Ledger()
    book.record('SKU-9', RECEIVE, 4)
    book.record('SKU-9', SHIP, 4)
    book.record('SKU-9', ADJUST, -3, note='damaged, written off twice')
    assert book.balance('SKU-9') == -3
    assert audit.negative_skus(book) == ['SKU-9']
'''

register(Repo(
    id="ledger",
    title="ledger: the pallet that was sold twice",
    difficulty="MEDIUM",
    shapes=("ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="array_caverns",
    tags=("state", "invariants"),
    target_seconds=900,
    brief=(
        "On Friday the picking service shipped five of a SKU we held three of. "
        "Nothing in the book stopped it, and InsufficientStock has been sitting "
        "in book.py unraised since whoever wrote it moved teams.\n\n"
        "Make a SHIP that exceeds the balance raise InsufficientStock, with the "
        "sku, the quantity wanted and what was actually available. The book is "
        "append-only, so a refused movement must leave nothing behind."
    ),
    start_file="ledger/book.py",
    start_note=(
        "Ledger.record is the only way a movement gets into the book. Read the "
        "sign policy in its docstring, and then read the last test in "
        "tests/test_audit.py before you decide what `too low` means."
    ),
    lesson=(
        "There is a general rule here that is wrong: `no movement may take the "
        "balance below zero`. Adjustments are how a bad stocktake gets recorded "
        "and they go negative routinely. The guard belongs on SHIP alone, which "
        "is what the ticket actually asked for."
    ),
    files={
        "ledger/__init__.py": src(_LEDGER_INIT),
        "ledger/book.py": src(_LEDGER_BOOK),
        "ledger/audit.py": src(_LEDGER_AUDIT),
    },
    tests={
        "tests/test_book.py": src(_LEDGER_TEST_BOOK),
        "tests/test_audit.py": src(_LEDGER_TEST_AUDIT),
    },
    targets=("tests/test_book.py::test_shipping_more_than_we_hold_is_refused",),
    patch=(
        Fix(
            path="ledger/book.py",
            old="""        entry = {"sku": sku, "kind": kind, "qty": qty, "note": note}""",
            new="""        if kind == SHIP:
            # Only SHIP. An adjustment is allowed below zero: that is how a
            # double write-off gets recorded, and audit.negative_skus is how
            # anyone finds out about it.
            available = self.balance(sku)
            if qty > available:
                raise InsufficientStock(sku, qty, available)
        entry = {"sku": sku, "kind": kind, "qty": qty, "note": note}""",
            why=("Checked before the append, so the refusal leaves the book "
                 "untouched, and scoped to SHIP, so reconciliation can still "
                 "record a shelf that disagrees with us."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# retrying — the wrapper that retries things it should not
# ---------------------------------------------------------------------------

_RETRY_INIT = r'''
"""retrying: call it again, but not forever, and not for everything."""
from .policy import Policy
from .runner import RetryError, call

__all__ = ["Policy", "call", "RetryError"]
'''

_RETRY_POLICY = r'''
"""How long to wait, and whether to bother.

The delay grows exponentially from `base`, doubling each attempt, and is capped
at `max_delay`.
"""


class Policy:
    """Retry settings. Pass one to runner.call, or accept the defaults."""

    def __init__(self, attempts=3, base=0.1, max_delay=2.0, jitter=0.0,
                 no_retry=()):
        self.attempts = attempts
        self.base = base
        self.max_delay = max_delay
        self.jitter = jitter                 # accepted, not yet wired up
        self.no_retry = tuple(no_retry)

    def delay_for(self, attempt):
        """Seconds to wait before retry number `attempt`, counting from 1."""
        if attempt < 1:
            return 0.0
        delay = self.base * attempt
        return min(delay, self.max_delay)

    def should_retry(self, exc, attempt):
        """Whether another attempt is allowed after `attempt` failures."""
        return attempt < self.attempts

    def describe(self):
        return "%d attempts, %.2fs base, %.2fs cap" % (
            self.attempts, self.base, self.max_delay)
'''

_RETRY_RUNNER = r'''
"""Call something that might not work the first time.

`sleep` is injected so that tests do not actually wait. Nothing else in this
package is allowed to look at the clock.
"""
import time

from .policy import Policy


class RetryError(Exception):
    """Every attempt was used up. `last` is the exception that ended it."""

    def __init__(self, attempts, last):
        super().__init__("gave up after %d attempts: %r" % (attempts, last))
        self.attempts = attempts
        self.last = last


def call(fn, *args, policy=None, sleep=None, **kwargs):
    """Call fn until it returns, or until the policy runs out of patience."""
    policy = policy or Policy()
    sleep = sleep or time.sleep
    attempt = 0
    last = None
    while True:
        attempt += 1
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last = exc
            if not policy.should_retry(exc, attempt):
                raise RetryError(attempt, exc) from exc
            sleep(policy.delay_for(attempt))


def call_quietly(fn, *args, default=None, **kwargs):
    # Used by the metrics flusher, which would rather have a hole in a graph
    # than a page at three in the morning.
    try:
        return call(fn, *args, **kwargs)
    except RetryError:
        return default
'''

_RETRY_TEST_POLICY = r'''
"""Policy tests. The numbers below are what the runbook quotes, so they are
load-bearing: an on-call engineer reads `0.1, 0.2, 0.3` off the wiki and
expects the log to agree with it."""
from retrying import Policy


def test_delays_match_the_runbook():
    policy = Policy(attempts=4, base=0.1, max_delay=2.0)
    assert round(policy.delay_for(1), 4) == 0.1
    assert round(policy.delay_for(2), 4) == 0.2
    assert round(policy.delay_for(3), 4) == 0.3


def test_delay_is_capped():
    policy = Policy(attempts=100, base=1.0, max_delay=2.5)
    assert policy.delay_for(9) == 2.5


def test_the_zeroth_delay_is_nothing():
    assert Policy().delay_for(0) == 0.0


def test_should_retry_counts_attempts():
    policy = Policy(attempts=2)
    assert policy.should_retry(ValueError("x"), 1) is True
    assert policy.should_retry(ValueError("x"), 2) is False
'''

_RETRY_TEST_RUNNER = r'''
"""Runner tests.

The last one is the ticket. A config typo raised KeyError and the runner spent
four attempts and six seconds proving that the key was still missing, on every
request, for an hour.
"""
from retrying import Policy, RetryError, call


class Flaky:
    """Fails `fails` times, then returns `value`."""

    def __init__(self, fails, value="ok", exc=None):
        self.fails = fails
        self.value = value
        self.exc = exc or ValueError("not yet")
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return self.value


def test_returns_on_the_first_success():
    fn = Flaky(0)
    assert call(fn, sleep=lambda s: None) == "ok"
    assert fn.calls == 1


def test_retries_until_it_works():
    fn = Flaky(2)
    naps = []
    assert call(fn, policy=Policy(attempts=5, base=0.1), sleep=naps.append) == "ok"
    assert fn.calls == 3
    assert [round(n, 4) for n in naps] == [0.1, 0.2]


def test_gives_up_and_wraps_the_last_failure():
    fn = Flaky(99)
    naps = []
    try:
        call(fn, policy=Policy(attempts=3, base=0.1), sleep=naps.append)
    except RetryError as exc:
        assert exc.attempts == 3
        assert isinstance(exc.last, ValueError)
    else:
        raise AssertionError("three failures should exhaust three attempts")
    assert fn.calls == 3
    assert [round(n, 4) for n in naps] == [0.1, 0.2]


def test_an_ordinary_error_is_still_retried():
    # Most failures here are transient and a plain ValueError is one of them.
    fn = Flaky(1)
    assert call(fn, policy=Policy(attempts=3, base=0.0), sleep=lambda s: None) == "ok"
    assert fn.calls == 2


def test_a_fatal_error_is_not_retried_and_comes_out_as_itself():
    fn = Flaky(99, exc=KeyError("database_url"))
    naps = []
    policy = Policy(attempts=4, base=0.1, no_retry=(KeyError,))
    try:
        call(fn, policy=policy, sleep=naps.append)
    except KeyError:
        pass
    except RetryError:
        raise AssertionError("a fatal error must not be wrapped in RetryError")
    assert fn.calls == 1
    assert naps == []
'''

register(Repo(
    id="retrying",
    title="retrying: four attempts at a typo",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="debugging_dungeon",
    tags=("control-flow", "exceptions"),
    target_seconds=900,
    brief=(
        "A missing config key raised KeyError. The runner retried it four "
        "times, six seconds a request, for an hour, and then reported the "
        "outage as a RetryError with the real cause two frames down.\n\n"
        "Policy already accepts a `no_retry` tuple of exception types and "
        "nothing consults it. Make those exceptions stop the loop at once and "
        "propagate unchanged — not wrapped, not delayed, not retried."
    ),
    start_file="retrying/runner.py",
    start_note=(
        "One `except` block decides everything that happens after a failure. "
        "Note that the existing tests pin two separate promises about it: how "
        "many times it sleeps, and what comes out when the attempts run out."
    ),
    lesson=(
        "`should_retry` looks like the right place and is not. It answers "
        "`may I try again`, and the runner turns a no into a RetryError. A "
        "fatal exception is not a no — it is a different question, and it "
        "needs its own branch before that one."
    ),
    files={
        "retrying/__init__.py": src(_RETRY_INIT),
        "retrying/policy.py": src(_RETRY_POLICY),
        "retrying/runner.py": src(_RETRY_RUNNER),
    },
    tests={
        "tests/test_policy.py": src(_RETRY_TEST_POLICY),
        "tests/test_runner.py": src(_RETRY_TEST_RUNNER),
    },
    targets=("tests/test_runner.py::"
             "test_a_fatal_error_is_not_retried_and_comes_out_as_itself",),
    patch=(
        Fix(
            path="retrying/runner.py",
            old="""            last = exc
            if not policy.should_retry(exc, attempt):""",
            new="""            last = exc
            # Before the attempt budget, not inside it: running out of
            # attempts produces a RetryError, and this is not that. The
            # caller asked for this exception, so it leaves as itself.
            if policy.no_retry and isinstance(exc, policy.no_retry):
                raise
            if not policy.should_retry(exc, attempt):""",
            why=("A separate branch, ahead of the budget check, so the two "
                 "promises the existing tests pin — the sleep sequence and "
                 "the RetryError on exhaustion — are both untouched."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# confmerge — layered configuration, and a dict two objects are sharing
# ---------------------------------------------------------------------------

_CONF_INIT = r'''
"""confmerge: defaults, then the site file, then the environment."""
from .layers import apply_env, defaults, resolve
from .merge import merge

__all__ = ["merge", "defaults", "resolve", "apply_env"]
'''

_CONF_MERGE = r'''
"""Deep merge for configuration layers.

`merge(base, override)` returns a new dict. Neither argument is modified.
Nested dicts are merged key by key; everything else is replaced outright.
"""


def merge(base, override):
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def flatten(config, prefix=""):
    # Used by the old /config debug page, which now renders JSON directly.
    flat = {}
    for key, value in sorted(config.items()):
        name = prefix + key
        if isinstance(value, dict):
            flat.update(flatten(value, name + "."))
        else:
            flat[name] = value
    return flat
'''

_CONF_LAYERS = r'''
"""The layers, in order: packaged defaults, then the site file, then the
environment. Later wins. The environment layer only ever sets scalars.
"""
import os

from .merge import merge

PREFIX = 'GAUNTLET_'

DEFAULTS = {
    'server': {'host': '127.0.0.1', 'port': 8080, 'workers': 2},
    'logging': {'level': 'INFO', 'handlers': ['console']},
    'plugins': ['core'],
    'features': {},
}


def defaults():
    """The packaged defaults. Callers get their own copy to scribble on."""
    return DEFAULTS


def _coerce(raw):
    """Environment variables are strings. Config is not."""
    if raw.lower() in ('true', 'yes', 'on'):
        return True
    if raw.lower() in ('false', 'no', 'off'):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def apply_env(config, environ=None):
    """Overlay GAUNTLET_* variables onto an already merged config, in place.

    GAUNTLET_SERVER_PORT lands at config['server']['port']. The daemon holds
    one config object for the lifetime of the process and reloads the
    environment onto it, so this deliberately returns the object it was given.
    """
    environ = os.environ if environ is None else environ
    for name in sorted(environ):
        if not name.startswith(PREFIX):
            continue
        path = name[len(PREFIX):].lower().split('_')
        node = config
        for part in path[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[path[-1]] = _coerce(environ[name])
    return config


def resolve(site=None, environ=None):
    """The whole stack, resolved into one config dict."""
    config = merge(defaults(), site or {})
    return apply_env(config, environ)
'''

_CONF_TEST_MERGE = r'''
"""Merge tests.

Note the import: confmerge/__init__.py binds the name `merge` to the function,
which shadows the module of the same name. Import the function directly.
"""
from confmerge.merge import merge


def test_scalars_from_the_override_win():
    assert merge({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3}


def test_nested_dicts_are_merged_not_replaced():
    out = merge({"server": {"host": "localhost", "port": 80}},
                {"server": {"port": 8080}})
    assert out == {"server": {"host": "localhost", "port": 8080}}


def test_lists_replace_rather_than_accumulate():
    # Deliberate. A site file that names three log handlers means exactly
    # those three, not those three plus whatever shipped in the defaults.
    out = merge({"handlers": ["console", "syslog"]}, {"handlers": ["file"]})
    assert out["handlers"] == ["file"]


def test_neither_argument_is_modified():
    base = {"server": {"port": 80}}
    over = {"server": {"port": 8080}}
    merge(base, over)
    assert base == {"server": {"port": 80}}
    assert over == {"server": {"port": 8080}}


def test_plugin_lists_accumulate_across_layers():
    # Plugins are additive: a site file adds to what the product ships with,
    # it does not replace it. Every other list still replaces.
    out = merge({"plugins": ["core"], "logging": {"handlers": ["console"]}},
                {"plugins": ["metrics"], "logging": {"handlers": ["file"]}})
    assert out["plugins"] == ["core", "metrics"]
    assert out["logging"]["handlers"] == ["file"]
'''

_CONF_TEST_LAYERS = r'''
"""Layer tests.

The last one is the ticket. The workers count crept up between two reloads in
production and nobody could reproduce it from a single call.
"""
from confmerge import layers


def test_resolve_with_nothing_is_the_defaults():
    config = layers.resolve()
    assert config['server']['host'] == '127.0.0.1'
    assert config['server']['port'] == 8080
    assert config['logging']['level'] == 'INFO'


def test_the_site_file_beats_the_defaults():
    config = layers.resolve(site={'server': {'port': 7000}})
    assert config['server']['port'] == 7000
    assert config['server']['host'] == '127.0.0.1'


def test_the_environment_beats_the_site_file():
    config = layers.resolve(site={'server': {'port': 7000}},
                            environ={'GAUNTLET_SERVER_PORT': '9000'})
    assert config['server']['port'] == 9000


def test_values_are_coerced_out_of_their_strings():
    config = layers.resolve(site={'server': {'port': 7000}},
                            environ={'GAUNTLET_SERVER_PORT': '9000',
                                     'GAUNTLET_FEATURES_BETA': 'true'})
    assert config['server']['port'] == 9000
    assert config['features']['beta'] is True


def test_variables_without_the_prefix_are_ignored():
    config = layers.resolve(site={'server': {'port': 7000}},
                            environ={'PATH': '/usr/bin', 'HOME': '/root'})
    assert 'path' not in config


def test_apply_env_updates_the_config_object_it_was_given():
    # The daemon holds one config object for the life of the process and
    # reloads the environment onto it while requests are in flight. Handing
    # back a copy would leave every one of those requests on the old config.
    config = {'server': {'port': 8080}}
    same = layers.apply_env(config, {'GAUNTLET_SERVER_PORT': '9001'})
    assert same is config
    assert config['server']['port'] == 9001


def test_resolve_does_not_write_on_the_packaged_defaults():
    first = layers.resolve(environ={'GAUNTLET_SERVER_WORKERS': '16'})
    assert first['server']['workers'] == 16
    second = layers.resolve()
    assert second['server']['workers'] == 2, 'the packaged defaults were edited'
'''

register(Repo(
    id="confmerge",
    title="confmerge: the config that remembered",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="hashmap_highlands",
    tags=("dicts", "aliasing"),
    target_seconds=1080,
    brief=(
        "Two tickets, one repository.\n\n"
        "1. The worker count crept up across reloads in production and nobody "
        "could reproduce it from a single call. resolve() is somehow making "
        "the next resolve() come out different.\n\n"
        "2. Plugins must accumulate across layers: a site file that names a "
        "plugin adds to what the product ships with. Every other list still "
        "replaces, and the suite already says so."
    ),
    start_file="confmerge/layers.py",
    start_note=(
        "resolve() is three lines and calls two things. One of them promises "
        "in its docstring to hand back a copy. Check whether it does, and "
        "count how many dicts a shallow copy actually copies."
    ),
    lesson=(
        "`dict(base)` copies one level. Every nested dict in the result is the "
        "same object the defaults are holding, so the in-place environment "
        "overlay — which is in-place on purpose, and a test pins that — writes "
        "straight through into the packaged defaults. The fix goes where the "
        "copy is promised, not where the write happens."
    ),
    files={
        "confmerge/__init__.py": src(_CONF_INIT),
        "confmerge/merge.py": src(_CONF_MERGE),
        "confmerge/layers.py": src(_CONF_LAYERS),
    },
    tests={
        "tests/test_merge.py": src(_CONF_TEST_MERGE),
        "tests/test_layers.py": src(_CONF_TEST_LAYERS),
    },
    targets=(
        "tests/test_layers.py::test_resolve_does_not_write_on_the_packaged_defaults",
        "tests/test_merge.py::test_plugin_lists_accumulate_across_layers",
    ),
    patch=(
        Fix(
            path="confmerge/layers.py",
            old="""import os

from .merge import merge""",
            new="""import copy
import os

from .merge import merge""",
            why="",
        ),
        Fix(
            path="confmerge/layers.py",
            old="""    \"\"\"The packaged defaults. Callers get their own copy to scribble on.\"\"\"
    return DEFAULTS""",
            new="""    \"\"\"The packaged defaults. Callers get their own copy to scribble on.\"\"\"
    # Deep, not shallow: apply_env writes into the nested dicts, and it is
    # required to do that in place. A shallow copy shares them with DEFAULTS.
    return copy.deepcopy(DEFAULTS)""",
            why=("The docstring already promised this. The only thing that "
                 "changed is that it is now true, and apply_env keeps the "
                 "in-place contract the daemon depends on."),
        ),
        Fix(
            path="confmerge/merge.py",
            old="""def merge(base, override):
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):""",
            new="""# Lists under these keys accumulate across layers. Everything else replaces,
# which is what a site file naming three log handlers has always meant.
APPEND_KEYS = ("plugins",)


def merge(base, override):
    out = dict(base)
    for key, value in override.items():
        if key in APPEND_KEYS and isinstance(value, list) \\
                and isinstance(out.get(key), list):
            out[key] = list(out[key]) + list(value)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):""",
            why=("Keyed by name rather than by type. Appending every list "
                 "would have been one character shorter and would have broken "
                 "the handlers contract."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# salesreport — a CSV, a fixture on disk, and a zero that means "unknown"
# ---------------------------------------------------------------------------

_SALES_INIT = r'''
"""salesreport: turn the export into something finance will read."""
from .read import load
from .render import by_region, table, total

__all__ = ["load", "total", "by_region", "table"]
'''

_SALES_READ = r'''
"""Reading the sales export.

The export is a CSV with a header row: date, region, sku, units, amount.
`amount` is pounds and pence as a decimal string. It is sometimes empty,
because the upstream system writes the row when the order ships and prices it
when the invoice is raised, and those are not the same afternoon.
"""
import csv
import os

HEADER = ['date', 'region', 'sku', 'units', 'amount']

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(os.path.dirname(_HERE), 'data', 'sales.csv')


def _money(raw):
    """A price column as a float."""
    text = (raw or '').strip()
    if not text:
        return 0.0
    return round(float(text.replace(',', '')), 2)


def load(path=None):
    """Read the export.

    Returns (rows, problems). `problems` is a list of (line number, column)
    pairs for cells we could not use; the line number is the one an editor
    shows, counting the header as line 1.
    """
    path = path or DEFAULT_PATH
    rows = []
    problems = []
    with open(path, newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        for number, raw in enumerate(reader, start=2):
            row = dict(raw)
            row['units'] = int(row['units'] or 0)
            row['amount'] = _money(row['amount'])
            rows.append(row)
    return rows, problems


def regions(rows):
    return sorted({r['region'] for r in rows})
'''

_SALES_RENDER = r'''
"""Rendering. Nothing in here reads a file; hand it the rows from read.load.

Second pair of hands on this file, hence the different quotes. Sorry.
"""


def total(rows):
    """Sum of the amount column."""
    out = 0.0
    for row in rows:
        out += row["amount"]
    return round(out, 2)


def by_region(rows):
    """Region -> total, in alphabetical order of region."""
    sums = {}
    for row in rows:
        sums.setdefault(row["region"], 0.0)
        sums[row["region"]] += row["amount"]
    return {k: round(v, 2) for k, v in sorted(sums.items())}


def table(rows, columns=("region", "sku", "units", "amount")):
    """A fixed-width table, header included, one line per row.

    Columns are padded to the widest cell in the column. Numbers are not right
    aligned, which finance have mentioned, twice.
    """
    cells = [[str(c) for c in columns]]
    for row in rows:
        cells.append([str(row[c]) for c in columns])
    widths = [max(len(line[i]) for line in cells) for i in range(len(columns))]
    lines = []
    for line in cells:
        lines.append("  ".join(v.ljust(widths[i]) for i, v in enumerate(line)).rstrip())
    return "\n".join(lines)
'''

_SALES_CSV = r'''
date,region,sku,units,amount
2024-04-01,north,SKU-1,3,45.00
2024-04-01,south,SKU-2,1,12.50
2024-04-02,north,SKU-3,2,
2024-04-02,east,SKU-1,5,75.00
2024-04-03,south,SKU-4,1,9.99
2024-04-03,north,SKU-2,4,
2024-04-04,east,SKU-5,2,30.00
'''

_SALES_TEST_READ = r'''
"""Reader tests.

The last one is the ticket. Finance reconciled April against the warehouse and
found two orders that our report says were worth nothing at all.
"""
from salesreport import read


def test_every_row_comes_back():
    rows, _ = read.load()
    assert len(rows) == 7
    assert rows[0]['region'] == 'north'
    assert rows[0]['sku'] == 'SKU-1'


def test_units_are_integers():
    rows, _ = read.load()
    assert all(isinstance(r['units'], int) for r in rows)
    assert sum(r['units'] for r in rows) == 18


def test_regions_are_listed_once_each():
    rows, _ = read.load()
    assert read.regions(rows) == ['east', 'north', 'south']


def test_an_unpriced_row_is_reported_rather_than_counted_as_zero():
    rows, problems = read.load()
    # Two orders shipped in April and had not been invoiced when the export
    # ran. They are rows 4 and 7 of the file, counting the header as row 1.
    assert [p[0] for p in problems] == [4, 7]
    assert [p[1] for p in problems] == ['amount', 'amount']
    # The rows stay: the units are real even when the money is not known yet.
    assert len(rows) == 7
    assert [r['amount'] for r in rows].count(None) == 2
'''

_SALES_TEST_RENDER = r'''
"""Rendering tests. These are what finance signed off on in February."""
from salesreport import read, render


def test_total_is_the_april_number():
    rows, _ = read.load()
    assert render.total(rows) == 172.49


def test_by_region_is_alphabetical_and_adds_up():
    rows, _ = read.load()
    assert render.by_region(rows) == {'east': 105.0, 'north': 45.0, 'south': 22.49}


def test_the_table_has_a_header_and_a_line_per_row():
    rows, _ = read.load()
    lines = render.table(rows).splitlines()
    assert len(lines) == 8
    assert lines[0].split() == ['region', 'sku', 'units', 'amount']


def test_the_table_pads_every_column_to_the_widest_cell():
    rows = [{'region': 'north', 'sku': 'SKU-1', 'units': 3, 'amount': 45.0},
            {'region': 'e', 'sku': 'SKU-10', 'units': 12, 'amount': 5.0}]
    lines = render.table(rows).splitlines()
    assert lines[1] == 'north   SKU-1   3      45.0'
    assert lines[2] == 'e       SKU-10  12     5.0'
'''

register(Repo(
    id="salesreport",
    title="salesreport: two orders worth nothing at all",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="fields_of_syntax",
    tags=("csv", "files", "data"),
    target_seconds=900,
    brief=(
        "Finance reconciled April against the warehouse. Two orders shipped "
        "and our report says they were worth nothing, because the invoice had "
        "not been raised when the export ran and an empty price column becomes "
        "0.00 somewhere between the file and the total.\n\n"
        "An unpriced row must come back with amount None and be listed in the "
        "`problems` the reader already promises to return — as (line number, "
        "column), counting the header as line 1. The row itself stays: the "
        "units are real. Every number finance signed off in February must come "
        "out the same."
    ),
    start_file="salesreport/read.py",
    start_note=(
        "`load` builds a `problems` list, returns it, and never puts anything "
        "in it. Before you change what `amount` can hold, go and look at who "
        "reads it — render.py adds it up in two different functions."
    ),
    lesson=(
        "Widening a value from `float` to `float or None` is a change to a "
        "contract, not to a file. Two functions one module over add that "
        "column up, and both of them have a test with a real number in it. "
        "Finding the callers is the job; the edit is four lines."
    ),
    files={
        "salesreport/__init__.py": src(_SALES_INIT),
        "salesreport/read.py": src(_SALES_READ),
        "salesreport/render.py": src(_SALES_RENDER),
        "data/sales.csv": src(_SALES_CSV),
    },
    tests={
        "tests/test_read.py": src(_SALES_TEST_READ),
        "tests/test_render.py": src(_SALES_TEST_RENDER),
    },
    targets=("tests/test_read.py::"
             "test_an_unpriced_row_is_reported_rather_than_counted_as_zero",),
    patch=(
        Fix(
            path="salesreport/read.py",
            old="""def _money(raw):
    \"\"\"A price column as a float.\"\"\"
    text = (raw or '').strip()
    if not text:
        return 0.0
    return round(float(text.replace(',', '')), 2)""",
            new="""def _money(raw):
    \"\"\"A price column as a float, or None when the cell is empty.

    None means `we do not know yet`, which is a different fact from zero and
    is the entire reason this ticket exists.
    \"\"\"
    text = (raw or '').strip()
    if not text:
        return None
    return round(float(text.replace(',', '')), 2)""",
            why="",
        ),
        Fix(
            path="salesreport/read.py",
            old="""            row['amount'] = _money(row['amount'])
            rows.append(row)""",
            new="""            row['amount'] = _money(row['amount'])
            if row['amount'] is None:
                problems.append((number, 'amount'))
            rows.append(row)""",
            why="",
        ),
        Fix(
            path="salesreport/render.py",
            old="""    out = 0.0
    for row in rows:
        out += row["amount"]
    return round(out, 2)""",
            new="""    out = 0.0
    for row in rows:
        # An unpriced row contributes nothing to a total, which is also what
        # it did before. The difference is that now we know it was a decision.
        if row["amount"] is None:
            continue
        out += row["amount"]
    return round(out, 2)""",
            why=("The caller had to change too. This is the half of the "
                 "ticket that is not in the ticket."),
        ),
        Fix(
            path="salesreport/render.py",
            old="""    for row in rows:
        sums.setdefault(row["region"], 0.0)
        sums[row["region"]] += row["amount"]""",
            new="""    for row in rows:
        sums.setdefault(row["region"], 0.0)
        if row["amount"] is None:
            continue
        sums[row["region"]] += row["amount"]""",
            why="The second caller. There are exactly two.",
        ),
    ),
))


# ---------------------------------------------------------------------------
# tokengate — a rate limiter that quietly throws away fractions of a token
# ---------------------------------------------------------------------------

_GATE_INIT = r'''
"""tokengate: how many is too many, per client, per second."""
from .gate import Gate
from .limiter import TokenBucket

__all__ = ["TokenBucket", "Gate"]
'''

_GATE_LIMITER = r'''
"""One token bucket.

Tokens accumulate at `per_second` and are capped at `capacity`, which is also
the largest burst a caller can make after being idle. `now` is passed in
everywhere rather than read from the clock, so that the tests and the replay
tool can drive it.
"""


class TokenBucket:

    def __init__(self, capacity, per_second, now=0.0):
        self.capacity = capacity
        self.rate = per_second
        self.tokens = capacity
        self.updated = now

    def _refill(self, now):
        """Add whatever has accrued since the last call."""
        elapsed = now - self.updated
        if elapsed <= 0:
            # Clocks do go backwards. Nothing accrues; nothing is lost either.
            return
        gained = int(elapsed * self.rate)
        self.tokens = min(self.capacity, self.tokens + gained)
        self.updated = now

    def allow(self, cost=1, now=None):
        """Take `cost` tokens if they are there. A refusal costs nothing.

        cost=0 asks the question without taking anything, which is what the
        admin dashboard does when it colours a client red.
        """
        self._refill(self.updated if now is None else now)
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

    def state(self):
        return {'tokens': self.tokens, 'capacity': self.capacity,
                'updated': self.updated}
'''

_GATE_GATE = r'''
"""Per-client gating.

One bucket per key, made on first sight. Keys are whatever the caller uses to
identify a client: an API token, an account id, an IP address in the bad old
days before the proxy.
"""
from .limiter import TokenBucket


class Gate:

    def __init__(self, capacity=10, per_second=5.0, now=0.0):
        self.capacity = capacity
        self.per_second = per_second
        self.started = now
        self.buckets = {}
        self.refused = 0

    def _bucket(self, key, now):
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(self.capacity, self.per_second, now)
        return self.buckets[key]

    def check(self, key, now, cost=1):
        """True if this request may proceed. Counts refusals as it goes."""
        ok = self._bucket(key, now).allow(cost, now)
        if not ok:
            self.refused += 1
        return ok

    def peek(self, key, now):
        """Whether the client is currently over its limit, without spending."""
        return self._bucket(key, now).allow(0, now)

    def retry_after(self, key, now):
        """Roughly how long until one more token exists. Zero if there is one."""
        bucket = self._bucket(key, now)
        if bucket.tokens >= 1:
            return 0.0
        return round((1 - bucket.tokens) / bucket.rate, 3)

    def forget(self, key):
        # The cleanup job calls this for clients we have not seen in an hour.
        self.buckets.pop(key, None)
'''

_GATE_TEST_LIMITER = r'''
"""Bucket tests.

The last one is the ticket. A client on the 2-per-second plan, polling four
times a second, was refused every single request for eleven minutes.
"""
from tokengate import TokenBucket


def test_a_fresh_bucket_is_full():
    bucket = TokenBucket(capacity=3, per_second=1.0, now=0.0)
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False


def test_a_burst_never_exceeds_capacity():
    # Idle for a fortnight, come back, and you still only get `capacity`.
    bucket = TokenBucket(capacity=3, per_second=1.0, now=0.0)
    allowed = [bucket.allow(now=1000.0) for _ in range(10)]
    assert allowed.count(True) == 3


def test_a_refusal_costs_nothing():
    bucket = TokenBucket(capacity=1, per_second=1.0, now=0.0)
    assert bucket.allow(now=0.0) is True
    assert bucket.allow(now=0.0) is False
    assert bucket.allow(now=0.0) is False
    # One second later exactly one token exists, which would not be true if a
    # refusal had been quietly charging the client anyway.
    assert bucket.allow(now=1.0) is True
    assert bucket.allow(now=1.0) is False


def test_cost_zero_is_a_question_not_a_withdrawal():
    bucket = TokenBucket(capacity=2, per_second=1.0, now=0.0)
    assert bucket.allow(cost=0, now=0.0) is True
    assert bucket.allow(cost=0, now=0.0) is True
    assert bucket.state()['tokens'] == 2


def test_a_steady_client_gets_the_rate_it_was_promised():
    # Two per second, asked four times a second, starting from empty: every
    # other request should live.
    bucket = TokenBucket(capacity=2, per_second=2.0, now=0.0)
    bucket.tokens = 0
    verdicts = [bucket.allow(now=0.25 * i) for i in range(1, 9)]
    assert verdicts == [False, True, False, True, False, True, False, True]
'''

_GATE_TEST_GATE = r'''
"""Gate tests: the per-client layer on top of the bucket."""
from tokengate import Gate


def test_clients_do_not_share_a_budget():
    gate = Gate(capacity=2, per_second=1.0, now=0.0)
    assert gate.check('alice', 0.0) is True
    assert gate.check('alice', 0.0) is True
    assert gate.check('alice', 0.0) is False
    assert gate.check('bob', 0.0) is True


def test_refusals_are_counted():
    gate = Gate(capacity=1, per_second=1.0, now=0.0)
    gate.check('alice', 0.0)
    gate.check('alice', 0.0)
    gate.check('alice', 0.0)
    assert gate.refused == 2


def test_peek_does_not_spend_a_token():
    gate = Gate(capacity=1, per_second=1.0, now=0.0)
    assert gate.peek('alice', 0.0) is True
    assert gate.peek('alice', 0.0) is True
    assert gate.check('alice', 0.0) is True


def test_retry_after_is_zero_while_the_client_still_has_budget():
    gate = Gate(capacity=2, per_second=4.0, now=0.0)
    assert gate.retry_after('alice', 0.0) == 0.0


def test_forgetting_a_client_gives_it_a_fresh_bucket():
    gate = Gate(capacity=1, per_second=1.0, now=0.0)
    assert gate.check('alice', 0.0) is True
    assert gate.check('alice', 0.0) is False
    gate.forget('alice')
    assert gate.check('alice', 0.0) is True
'''

register(Repo(
    id="tokengate",
    title="tokengate: refused for eleven minutes",
    difficulty="HARD",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="complexity_tower",
    tags=("arithmetic", "state", "time"),
    target_seconds=1500,
    brief=(
        "A customer on the two-per-second plan polls four times a second. They "
        "should be refused every other request. They were refused every "
        "request, for eleven minutes, until the process restarted.\n\n"
        "The symptom is in the gate. The cause is not. Find it, and note that "
        "two of the existing tests are pinning promises about what a refusal "
        "costs and how big a burst can get, both of which are easy to break "
        "while you are in there."
    ),
    start_file="tokengate/limiter.py",
    start_note=(
        "_refill is six lines. Work out, on paper, what it does when a quarter "
        "of a second has passed at two tokens a second, and then what it does "
        "to `updated` while it is doing it."
    ),
    lesson=(
        "`int()` on an accrual is a rounding decision that also throws away "
        "the remainder, and the line underneath it advances the clock as "
        "though the remainder had been paid out. Any client whose polling "
        "interval is shorter than one whole token starves forever."
    ),
    files={
        "tokengate/__init__.py": src(_GATE_INIT),
        "tokengate/limiter.py": src(_GATE_LIMITER),
        "tokengate/gate.py": src(_GATE_GATE),
    },
    tests={
        "tests/test_limiter.py": src(_GATE_TEST_LIMITER),
        "tests/test_gate.py": src(_GATE_TEST_GATE),
    },
    targets=("tests/test_limiter.py::"
             "test_a_steady_client_gets_the_rate_it_was_promised",),
    patch=(
        Fix(
            path="tokengate/limiter.py",
            old="""        gained = int(elapsed * self.rate)
        self.tokens = min(self.capacity, self.tokens + gained)""",
            new="""        # Fractions of a token are kept. Truncating here and advancing
        # `updated` anyway is how a client polling faster than one whole
        # token per interval accrues nothing, forever.
        gained = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + gained)""",
            why=("The cap stays, so a long idle period still buys exactly one "
                 "burst, and `allow` still checks before it subtracts, so a "
                 "refusal still costs nothing."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# lrucache — recency, and the one reader that must not disturb it
# ---------------------------------------------------------------------------

_LRU_INIT = r'''
"""lrucache: keep the useful ones, drop the rest."""
from .stats import hit_rate, report
from .store import LRUCache

__all__ = ["LRUCache", "hit_rate", "report"]
'''

_LRU_STORE = r'''
"""A least-recently-used cache.

Recency is the insertion order of the backing dict, which Python guarantees.
Touching a key means deleting it and putting it back, which moves it to the
end; the front of the dict is therefore the coldest thing we hold.
"""

MISSING = object()


class LRUCache:

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("a cache of nothing is not a cache")
        self.capacity = capacity
        self._data = {}
        self.hits = 0
        self.misses = 0
        self.evicted = 0

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data

    def _lookup(self, key):
        """Fetch, with no opinion about what the fetch means."""
        return self._data.get(key, MISSING)

    def get(self, key, default=None):
        """Read a key, and count whether it was there."""
        value = self._lookup(key)
        if value is MISSING:
            self.misses += 1
            return default
        self.hits += 1
        return value

    def peek(self, key, default=None):
        """Read a key without disturbing anything.

        The admin endpoint dumps the whole cache through this on every scrape.
        If peeking counted as use, the monitoring would be deciding what stays
        in the cache, which it emphatically must not.
        """
        value = self._lookup(key)
        return default if value is MISSING else value

    def put(self, key, value):
        if key in self._data:
            del self._data[key]
        self._data[key] = value
        while len(self._data) > self.capacity:
            coldest = next(iter(self._data))
            del self._data[coldest]
            self.evicted += 1

    def keys(self):
        """Keys, coldest first."""
        return list(self._data)

    def clear(self):
        self._data.clear()
'''

_LRU_STATS = r'''
"""Numbers about a cache, for the dashboard.

Nothing in here may change the cache. It is called on a timer, from a thread
that is not serving anybody, and it reads through peek for that reason.
"""


def hit_rate(cache):
    """Hits as a fraction of lookups, rounded to three places."""
    lookups = cache.hits + cache.misses
    if not lookups:
        return 0.0
    return round(cache.hits / lookups, 3)


def report(cache):
    """One line per key, coldest first, plus a summary."""
    lines = []
    for key in cache.keys():
        lines.append('%s = %r' % (key, cache.peek(key)))
    lines.append('%d/%d used, %d evicted, hit rate %.3f' % (
        len(cache), cache.capacity, cache.evicted, hit_rate(cache)))
    return '\n'.join(lines)


def coldest(cache, count=1):
    # The eviction preview on the admin page. Nobody has opened it in months.
    return cache.keys()[:count]
'''

_LRU_TEST_STORE = r'''
"""Cache tests.

The last one is the ticket. The session cache is evicting sessions that are in
use, every few minutes, and the graph of it looks like the cache is ignoring
reads entirely.
"""
from lrucache import LRUCache


def test_it_holds_what_you_put_in_it():
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert len(cache) == 1


def test_a_miss_returns_the_default_and_stores_nothing():
    cache = LRUCache(2)
    assert cache.get("nope", "fallback") == "fallback"
    assert len(cache) == 0
    assert "nope" not in cache


def test_the_coldest_key_is_evicted_when_it_is_full():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.keys() == ["b", "c"]
    assert cache.evicted == 1


def test_writing_a_key_again_makes_it_the_warmest():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 99)
    cache.put("c", 3)
    assert cache.keys() == ["a", "c"]
    assert cache.get("a") == 99


def test_peeking_does_not_change_what_gets_evicted():
    # The monitoring thread dumps the cache through peek on every scrape. If
    # that counted as use, the dashboard would be choosing what stays in the
    # cache, and it would always choose everything.
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.peek("a") == 1
    assert cache.peek("a") == 1
    cache.put("c", 3)
    assert cache.keys() == ["b", "c"]


def test_reading_a_key_keeps_it_warm():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.keys() == ["a", "c"]
'''

_LRU_TEST_STATS = r'''
"""Dashboard tests. All of these run against a cache the dashboard must not
disturb, so they assert the shape of the numbers and then assert that looking
at them changed nothing."""
from lrucache import LRUCache, hit_rate
from lrucache import stats


def _filled():
    cache = LRUCache(3)
    cache.put('a', 1)
    cache.put('b', 2)
    return cache


def test_hit_rate_of_an_untouched_cache_is_zero():
    assert hit_rate(LRUCache(3)) == 0.0


def test_hit_rate_counts_hits_over_lookups():
    cache = _filled()
    cache.get('a')
    cache.get('a')
    cache.get('zzz')
    assert hit_rate(cache) == 0.667


def test_report_lists_every_key_coldest_first():
    cache = _filled()
    lines = stats.report(cache).splitlines()
    assert lines[0] == "a = 1"
    assert lines[1] == "b = 2"
    assert lines[2].startswith('2/3 used, 0 evicted')


def test_reporting_does_not_touch_the_cache():
    cache = _filled()
    before = cache.keys()
    stats.report(cache)
    stats.report(cache)
    assert cache.keys() == before
    assert cache.hits == 0
    assert cache.misses == 0
'''

register(Repo(
    id="lrucache",
    title="lrucache: evicting the sessions people are using",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="hashmap_highlands",
    tags=("data-structures", "state"),
    target_seconds=900,
    brief=(
        "The session cache is throwing out sessions that are in active use. "
        "Writes move a key to the warm end. Reads, apparently, do not.\n\n"
        "Make reading a key keep it warm. There is a second reader in here "
        "that must keep behaving exactly as it does today, and a test that "
        "says why."
    ),
    start_file="lrucache/store.py",
    start_note=(
        "`get` and `peek` differ by four lines and one of those differences is "
        "the point of `peek`. Look at what they share before you change what "
        "they share."
    ),
    lesson=(
        "Two readers, deliberately different: one is use, one is observation. "
        "They share a private helper, which makes the helper the obvious place "
        "to put the fix and the one place it cannot go. The distinction has to "
        "be made where the intent is known, which is in the public method."
    ),
    files={
        "lrucache/__init__.py": src(_LRU_INIT),
        "lrucache/store.py": src(_LRU_STORE),
        "lrucache/stats.py": src(_LRU_STATS),
    },
    tests={
        "tests/test_store.py": src(_LRU_TEST_STORE),
        "tests/test_stats.py": src(_LRU_TEST_STATS),
    },
    targets=("tests/test_store.py::test_reading_a_key_keeps_it_warm",),
    patch=(
        Fix(
            path="lrucache/store.py",
            old="""        if value is MISSING:
            self.misses += 1
            return default
        self.hits += 1
        return value""",
            new="""        if value is MISSING:
            self.misses += 1
            return default
        # A read is a use, so the key goes back to the warm end. This cannot
        # live in _lookup: peek shares it, and peek must not disturb anything.
        del self._data[key]
        self._data[key] = value
        self.hits += 1
        return value""",
            why=("In `get`, where the caller's intent is known, rather than in "
                 "the shared helper, where it is not."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# taskflow — a dependency graph that calls a diamond a cycle
# ---------------------------------------------------------------------------

_FLOW_INIT = r'''
"""taskflow: work out what has to happen first."""
from .graph import CycleError, order
from .runner import run

__all__ = ["order", "CycleError", "run"]
'''

_FLOW_GRAPH = r'''
"""Dependency ordering.

A plan is {task name: [names it depends on]}. `order` returns a list in which
every task appears after everything it depends on. Ties are broken
alphabetically, so the same plan always produces the same order and a diff of
two plans is readable.
"""


class CycleError(Exception):
    """A plan that depends on itself, directly or round the houses."""


def order(tasks):
    done = []
    finished = set()
    active = set()

    def visit(name, trail):
        if name in active:
            raise CycleError(" -> ".join(trail + [name]))
        if name in finished:
            return
        active.add(name)
        for dependency in sorted(tasks.get(name, ())):
            visit(dependency, trail + [name])
        finished.add(name)
        done.append(name)

    for name in sorted(tasks):
        # Each root starts a fresh path, or the second root trips over the
        # first one. (This was the fix for the bug in March.)
        active.clear()
        visit(name, [])
    return done


def dependents(tasks, name):
    """Everything that would have to be re-run if `name` changed."""
    return sorted(t for t, deps in tasks.items() if name in deps)


def roots(tasks):
    # Tasks nothing depends on. Used by the old plan printer.
    depended = {d for deps in tasks.values() for d in deps}
    return sorted(t for t in tasks if t not in depended)
'''

_FLOW_RUNNER = r'''
"""Running a plan.

Each task is a zero-argument callable. Results are collected by name. A task
whose dependency failed is skipped rather than attempted, because the usual
outcome of running it anyway is a second, more confusing error.
"""
from .graph import order


class TaskFailed(Exception):
    def __init__(self, name, cause):
        super().__init__('%s failed: %r' % (name, cause))
        self.name = name
        self.cause = cause


def run(tasks, plan, stop_on_failure=False):
    """Run every task in dependency order.

    `tasks` is {name: callable}, `plan` is {name: [dependencies]}. Returns
    (results, failures): a dict of what each task returned, and a dict of the
    exceptions, both keyed by task name. Skipped tasks appear in neither.
    """
    results = {}
    failures = {}
    for name in order(plan):
        blocked = [d for d in plan.get(name, ()) if d in failures or d not in results]
        if blocked:
            continue
        try:
            results[name] = tasks[name]()
        except Exception as exc:
            failures[name] = exc
            if stop_on_failure:
                raise TaskFailed(name, exc) from exc
    return results, failures
'''

_FLOW_TEST_GRAPH = r'''
"""Ordering tests.

The last one is the ticket. The nightly build plan grew a second consumer of
the `fetch` step last week and has refused to start ever since, claiming a
cycle that three people have now failed to find on the whiteboard.
"""
from taskflow import CycleError, order


def test_a_chain_comes_out_in_order():
    assert order({"c": ["b"], "b": ["a"], "a": []}) == ["a", "b", "c"]


def test_independent_tasks_come_out_alphabetically():
    assert order({"b": [], "a": [], "c": []}) == ["a", "b", "c"]


def test_a_dependency_that_is_not_itself_a_task_still_orders():
    # Plans reference steps owned by other teams, which are not in this dict.
    assert order({"build": ["checkout"]}) == ["checkout", "build"]


def test_a_real_cycle_is_reported():
    try:
        order({"a": ["b"], "b": ["c"], "c": ["a"]})
    except CycleError as exc:
        assert "a" in str(exc)
        return
    raise AssertionError("a -> b -> c -> a is a cycle and must be refused")


def test_a_task_that_depends_on_itself_is_a_cycle():
    try:
        order({"a": ["a"]})
    except CycleError:
        return
    raise AssertionError("a depending on itself is a cycle")


def test_two_tasks_may_share_a_dependency():
    # The diamond: fetch is needed by both build and lint, and the artifact
    # needs both of those. This is an ordinary plan and not a cycle.
    plan = {"artifact": ["build", "lint"], "build": ["fetch"],
            "lint": ["fetch"], "fetch": []}
    assert order(plan) == ["fetch", "build", "lint", "artifact"]
'''

_FLOW_TEST_RUNNER = r'''
"""Runner tests. Linear plans only; the ordering itself is tested next door."""
from taskflow import run
from taskflow.runner import TaskFailed


def test_every_task_runs_and_its_result_is_kept():
    log = []
    tasks = {'a': lambda: log.append('a') or 1,
             'b': lambda: log.append('b') or 2}
    results, failures = run(tasks, {'b': ['a'], 'a': []})
    assert log == ['a', 'b']
    assert results == {'a': 1, 'b': 2}
    assert failures == {}


def test_a_failure_is_collected_not_raised():
    def boom():
        raise RuntimeError('disk full')
    results, failures = run({'a': boom}, {'a': []})
    assert results == {}
    assert isinstance(failures['a'], RuntimeError)


def test_a_task_whose_dependency_failed_does_not_run():
    log = []

    def boom():
        raise RuntimeError('nope')
    tasks = {'a': boom, 'b': lambda: log.append('b')}
    results, failures = run(tasks, {'b': ['a'], 'a': []})
    assert log == []
    assert 'b' not in results
    assert 'b' not in failures


def test_stop_on_failure_raises_with_the_task_name():
    def boom():
        raise RuntimeError('nope')
    try:
        run({'a': boom}, {'a': []}, stop_on_failure=True)
    except TaskFailed as exc:
        assert exc.name == 'a'
        assert isinstance(exc.cause, RuntimeError)
        return
    raise AssertionError('stop_on_failure should have raised')
'''

register(Repo(
    id="taskflow",
    title="taskflow: the cycle that is not there",
    difficulty="HARD",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="graph_wastes",
    tags=("graphs", "recursion"),
    target_seconds=1500,
    brief=(
        "The nightly build plan grew a second consumer of the `fetch` step "
        "last week. Since then it refuses to start, reporting a cycle. Three "
        "people have drawn the plan on a whiteboard and there is no cycle in "
        "it.\n\n"
        "Make a plan where two tasks share a dependency order correctly. A "
        "plan that really does contain a cycle must still be refused, and the "
        "suite checks two kinds."
    ),
    start_file="taskflow/graph.py",
    start_note=(
        "`order` is one recursive function with two sets in it. Ask what each "
        "set is for, note where one of them is cleared and where it is not, "
        "then trace the diamond by hand and watch the second visit to `fetch`."
    ),
    lesson=(
        "Two sets, two meanings: `finished` is where I have been, `active` is "
        "where I still am. A node is only evidence of a cycle while you are "
        "standing on it, and nothing takes it off the path on the way out. "
        "March noticed half of that and cleared the set once per root, which "
        "is why chains work and only a shared dependency inside one traversal "
        "misfires. Deleting the check is the fastest way to a green diamond "
        "and it deletes the only thing that catches a real cycle."
    ),
    files={
        "taskflow/__init__.py": src(_FLOW_INIT),
        "taskflow/graph.py": src(_FLOW_GRAPH),
        "taskflow/runner.py": src(_FLOW_RUNNER),
    },
    tests={
        "tests/test_graph.py": src(_FLOW_TEST_GRAPH),
        "tests/test_runner.py": src(_FLOW_TEST_RUNNER),
    },
    targets=("tests/test_graph.py::test_two_tasks_may_share_a_dependency",),
    patch=(
        Fix(
            path="taskflow/graph.py",
            old="""        finished.add(name)
        done.append(name)""",
            new="""        # Off the stack on the way out. `active` means `on the path I am
        # standing on right now`; leaving it set makes every shared
        # dependency look like a loop the second time it is reached.
        active.discard(name)
        finished.add(name)
        done.append(name)""",
            why=("One line, and the cycle detection it repairs is the same "
                 "cycle detection that still refuses a -> b -> c -> a."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# templater — a flag that is accepted and ignored
# ---------------------------------------------------------------------------

_TMPL_INIT = r'''
"""templater: fill in the blanks."""
from .render import MissingValue, UnknownFilter, render

__all__ = ["render", "MissingValue", "UnknownFilter"]
'''

_TMPL_RENDER = r'''
"""Filling {placeholders} in a string.

The syntax is {name} or {name|filter}. Filters live in filters.BY_NAME and are
applied left to right.
"""
import re

from .filters import BY_NAME

_TOKEN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(\|[a-zA-Z_]+)?\}")


class MissingValue(KeyError):
    """The template names a value that was not supplied."""


class UnknownFilter(KeyError):
    """The template names a filter that does not exist."""


def render(template, values, strict=True):
    """Fill in the placeholders and return the finished string.

    `strict` is for the preview mode the editor needs and is not wired up yet.
    """

    def replace(match):
        name = match.group(1)
        suffix = match.group(2)
        if name not in values:
            raise MissingValue(name)
        value = values[name]
        if suffix:
            filter_name = suffix[1:]
            if filter_name not in BY_NAME:
                raise UnknownFilter(filter_name)
            value = BY_NAME[filter_name](value)
        return str(value)

    return _TOKEN.sub(replace, template)


def placeholders(template):
    """Every name the template asks for, in order, without duplicates."""
    seen = []
    for match in _TOKEN.finditer(template):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen
'''

_TMPL_FILTERS = r'''
"""The filters a template may name.

Keep this module free of anything that can fail on ordinary input: a filter
that raises turns a rendering bug into a 500, and the renderer has no way to
say which placeholder did it.
"""


def upper(value):
    return str(value).upper()


def lower(value):
    return str(value).lower()


def title(value):
    return str(value).title()


def strip(value):
    return str(value).strip()


def money(value):
    """Pounds, two decimal places, no symbol. Finance add their own."""
    try:
        return '%.2f' % float(value)
    except (TypeError, ValueError):
        return str(value)


def initials(value):
    # For the avatar bubbles. The avatars were replaced with photographs.
    return ''.join(word[0].upper() for word in str(value).split() if word)


BY_NAME = {
    'upper': upper,
    'lower': lower,
    'title': title,
    'strip': strip,
    'money': money,
}
'''

_TMPL_TEST_RENDER = r'''
"""Renderer tests.

The last one is the ticket: the template editor wants a live preview, and the
preview cannot throw an exception every time somebody types an opening brace.
"""
from templater import MissingValue, UnknownFilter, render
from templater.render import placeholders


def test_a_placeholder_is_filled():
    assert render("hello {name}", {"name": "Ada"}) == "hello Ada"


def test_text_without_placeholders_survives():
    assert render("no braces here", {}) == "no braces here"


def test_a_filter_is_applied():
    assert render("{name|upper}", {"name": "ada"}) == "ADA"
    assert render("{cost|money}", {"cost": 3}) == "3.00"


def test_a_missing_value_is_an_error():
    try:
        render("hello {name}", {})
    except MissingValue:
        return
    raise AssertionError("a missing value must not render as anything")


def test_an_unknown_filter_is_an_error_in_preview_mode_too():
    # A filter that does not exist is a typo in the template, not a gap in the
    # data, and the preview is exactly where the author should be told.
    try:
        render("{name|shout}", {"name": "ada"}, strict=False)
    except UnknownFilter:
        return
    raise AssertionError("an unknown filter is always an error")


def test_placeholders_are_listed_in_order_without_repeats():
    assert placeholders("{a} {b} {a}") == ["a", "b"]


def test_preview_mode_leaves_a_gap_where_a_value_is_missing():
    assert render("{name} <{email}>", {"name": "Ada"}, strict=False) == "Ada <>"
    assert render("{a|upper}{b}", {"b": "!"}, strict=False) == "!"
    # A bad filter name is still a bad filter name, even over a gap.
    try:
        render("{nobody|shout}", {}, strict=False)
    except UnknownFilter:
        return
    raise AssertionError("the filter is checked before the value is missed")
'''

_TMPL_TEST_FILTERS = r'''
"""Filter tests. Every filter here has to survive whatever the data does."""
from templater import filters


def test_the_case_filters():
    assert filters.upper('ada') == 'ADA'
    assert filters.lower('ADA') == 'ada'
    assert filters.title('ada lovelace') == 'Ada Lovelace'


def test_strip_takes_the_edges_off():
    assert filters.strip('  padded  ') == 'padded'


def test_money_formats_numbers_and_gives_up_politely():
    assert filters.money(3) == '3.00'
    assert filters.money('4.5') == '4.50'
    assert filters.money('not a number') == 'not a number'


def test_every_registered_filter_survives_a_number():
    for name, fn in sorted(filters.BY_NAME.items()):
        assert isinstance(fn(12), str), name
'''

register(Repo(
    id="templater",
    title="templater: a flag nobody wired up",
    difficulty="MEDIUM",
    shapes=("ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="stringwood_labyrinth",
    tags=("strings", "flags"),
    target_seconds=900,
    brief=(
        "The template editor wants a live preview. It cannot have one while "
        "rendering a half-typed template raises MissingValue on every "
        "keystroke.\n\n"
        "`render` already takes a `strict` argument and already ignores it. "
        "With strict=False a placeholder with no value renders as nothing. A "
        "filter that does not exist is still an error — that is a typo in the "
        "template and the author is exactly who should hear about it."
    ),
    start_file="templater/render.py",
    start_note=(
        "One nested function does all of it. Note the order it does things in, "
        "and read the existing test about unknown filters in preview mode "
        "before you decide where the new branch goes."
    ),
    lesson=(
        "`values.get(name, \"\")` is the one-character fix and it is wrong "
        "twice: it forgives the strict path, which three callers depend on, "
        "and it reaches the value before the filter name has been checked, so "
        "a typo in a template stops being reported at exactly the moment "
        "somebody is typing it."
    ),
    files={
        "templater/__init__.py": src(_TMPL_INIT),
        "templater/render.py": src(_TMPL_RENDER),
        "templater/filters.py": src(_TMPL_FILTERS),
    },
    tests={
        "tests/test_render.py": src(_TMPL_TEST_RENDER),
        "tests/test_filters.py": src(_TMPL_TEST_FILTERS),
    },
    targets=("tests/test_render.py::"
             "test_preview_mode_leaves_a_gap_where_a_value_is_missing",),
    patch=(
        Fix(
            path="templater/render.py",
            old="""        name = match.group(1)
        suffix = match.group(2)
        if name not in values:
            raise MissingValue(name)
        value = values[name]
        if suffix:
            filter_name = suffix[1:]
            if filter_name not in BY_NAME:
                raise UnknownFilter(filter_name)
            value = BY_NAME[filter_name](value)
        return str(value)""",
            new="""        name = match.group(1)
        suffix = match.group(2)
        filter_name = suffix[1:] if suffix else ""
        # The filter name is checked first and unconditionally: it is a
        # property of the template, and preview mode forgives missing data,
        # not a misspelled filter.
        if filter_name and filter_name not in BY_NAME:
            raise UnknownFilter(filter_name)
        if name not in values:
            if strict:
                raise MissingValue(name)
            return ""
        value = values[name]
        if filter_name:
            value = BY_NAME[filter_name](value)
        return str(value)""",
            why=("`strict` is consulted in exactly one place, and the "
                 "template-level error is hoisted above it so that preview "
                 "mode never swallows a typo."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# validator — one entry point raises, the other must start collecting
# ---------------------------------------------------------------------------

_VALID_INIT = r'''
"""validator: say what is wrong with a document, and ideally all of it."""
from .rules import ValidationError, email, max_length, required
from .schema import assert_valid, validate

__all__ = ["validate", "assert_valid", "ValidationError",
           "required", "email", "max_length"]
'''

_VALID_RULES = r'''
"""The rules themselves.

Every rule is a callable taking (value, field name). A rule that is satisfied
returns None. A rule that is not raises ValidationError, which carries the
field it was about so the caller does not have to remember.
"""


class ValidationError(Exception):
    def __init__(self, field, message):
        super().__init__("%s %s" % (field, message))
        self.field = field
        self.message = message


def required(value, field):
    """Present and not empty. Zero is present. False is present."""
    if value is None or value == "":
        raise ValidationError(field, "is required")


def email(value, field):
    """Good enough for a signup form and no better.

    Anything stricter than this rejects addresses that genuinely exist, and we
    send a confirmation link anyway.
    """
    if value in (None, ""):
        return
    text = str(value)
    if text.count("@") != 1 or text.startswith("@") or text.endswith("@"):
        raise ValidationError(field, "is not an email address")
    if "." not in text.split("@")[1]:
        raise ValidationError(field, "is not an email address")


def max_length(limit):
    """Build a rule that refuses anything longer than `limit`."""

    def rule(value, field):
        if value is None:
            return
        if len(str(value)) > limit:
            raise ValidationError(field, "is longer than %d characters" % limit)

    rule.__name__ = "max_length_%d" % limit
    return rule


def one_of(*allowed):
    # Written for the country dropdown, which now validates in the browser.
    def rule(value, field):
        if value not in allowed:
            raise ValidationError(field, "is not one of %r" % (allowed,))

    return rule
'''

_VALID_SCHEMA = r'''
"""Applying a list of rules to a document.

A schema is {'fields': [{'name': ..., 'rules': [...]}, ...]}. Field order is
the order the form renders in, which is the order a person reads it in, which
is the order problems should be reported in.
"""


def validate(document, schema):
    """Check a document against a schema.

    Returns a list of problems. (It is always empty: the first rule that
    objects raises, and the exception leaves through here. The list is a
    leftover from when this collected them.)
    """
    for field in schema['fields']:
        value = document.get(field['name'])
        for rule in field['rules']:
            rule(value, field['name'])
    return []


def assert_valid(document, schema):
    """Raise on the first problem, or hand the document back.

    The HTTP layer calls this and turns a ValidationError into a 422 with the
    field name in it.
    """
    validate(document, schema)
    return document


def field_names(schema):
    return [f['name'] for f in schema['fields']]
'''

_VALID_TEST_RULES = r'''
"""Rule tests. Each rule is on its own and each one raises when it objects."""
from validator import ValidationError, email, max_length, required


def _refuses(rule, value, field='thing'):
    try:
        rule(value, field)
    except ValidationError as exc:
        assert exc.field == field
        return exc
    raise AssertionError('%r should have been refused' % (value,))


def test_required_refuses_nothing_at_all():
    exc = _refuses(required, None)
    assert exc.message == 'is required'
    _refuses(required, '')


def test_required_accepts_a_falsy_value_that_is_still_a_value():
    assert required(0, 'count') is None
    assert required(False, 'flag') is None


def test_email_wants_exactly_one_at_and_a_dot_after_it():
    assert email('ada@example.com', 'email') is None
    _refuses(email, 'ada.example.com', 'email')
    _refuses(email, 'ada@@example.com', 'email')
    _refuses(email, 'ada@localhost', 'email')


def test_email_leaves_an_empty_value_to_required():
    assert email('', 'email') is None
    assert email(None, 'email') is None


def test_max_length_measures_the_string_form():
    rule = max_length(3)
    assert rule('abc', 'bio') is None
    exc = _refuses(rule, 'abcd', 'bio')
    assert 'longer than 3' in exc.message
'''

_VALID_TEST_SCHEMA = r'''
"""Schema tests.

The last one is the ticket. The signup form corrects one field, resubmits,
and is told about the next one, four times running, and people give up on the
third.
"""
from validator import ValidationError, email, max_length, required
from validator import schema as schema_mod

SCHEMA = {'fields': [
    {'name': 'name', 'rules': [required, max_length(40)]},
    {'name': 'email', 'rules': [required, email]},
    {'name': 'bio', 'rules': [max_length(20)]},
]}

GOOD = {'name': 'Ada', 'email': 'ada@example.com', 'bio': 'short'}


def test_field_names_are_the_form_order():
    assert schema_mod.field_names(SCHEMA) == ['name', 'email', 'bio']


def test_a_good_document_has_nothing_wrong_with_it():
    assert schema_mod.validate(GOOD, SCHEMA) == []


def test_assert_valid_hands_back_a_good_document():
    assert schema_mod.assert_valid(GOOD, SCHEMA) is GOOD


def test_assert_valid_still_raises_on_the_first_problem():
    # The HTTP layer depends on this: it catches ValidationError and turns it
    # into a 422 naming one field. It has no idea what a list of problems is.
    bad = {'name': '', 'email': 'nope', 'bio': 'x' * 50}
    try:
        schema_mod.assert_valid(bad, SCHEMA)
    except ValidationError as exc:
        assert exc.field == 'name'
        return
    raise AssertionError('assert_valid must raise when the document is bad')


def test_every_problem_is_reported_not_only_the_first():
    bad = {'name': '', 'email': 'nope', 'bio': 'x' * 50}
    problems = schema_mod.validate(bad, SCHEMA)
    assert [p.field for p in problems] == ['name', 'email', 'bio']
    assert problems[0].message == 'is required'
    assert isinstance(problems[1], ValidationError)
'''

register(Repo(
    id="validator",
    title="validator: one problem at a time, forever",
    difficulty="HARD",
    shapes=("ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="debugging_dungeon",
    tags=("exceptions", "api-design"),
    target_seconds=1500,
    brief=(
        "Signup tells you about one bad field, you fix it, resubmit, and it "
        "tells you about the next one. Analytics say the third round is where "
        "people close the tab.\n\n"
        "`validate` must return every problem it found, in form order, one per "
        "field. There is a second entry point in that module and an HTTP layer "
        "that depends on it behaving exactly as it does today."
    ),
    start_file="validator/schema.py",
    start_note=(
        "The whole module is three functions and one of the docstrings already "
        "admits what is going on. Read both of the first two: they are not the "
        "same function with a different name, they are two different promises "
        "to two different callers."
    ),
    lesson=(
        "The rules raise, and that is their contract — tests/test_rules.py "
        "pins it eight times. Changing the rules so they return errors would "
        "be one edit instead of two and would rewrite an interface used "
        "everywhere. Collecting belongs at the layer that is allowed to have "
        "an opinion about how many problems a caller can face at once."
    ),
    files={
        "validator/__init__.py": src(_VALID_INIT),
        "validator/rules.py": src(_VALID_RULES),
        "validator/schema.py": src(_VALID_SCHEMA),
    },
    tests={
        "tests/test_rules.py": src(_VALID_TEST_RULES),
        "tests/test_schema.py": src(_VALID_TEST_SCHEMA),
    },
    targets=("tests/test_schema.py::test_every_problem_is_reported_not_only_the_first",),
    patch=(
        Fix(
            path="validator/schema.py",
            old="""def validate(document, schema):
    \"\"\"Check a document against a schema.

    Returns a list of problems. (It is always empty: the first rule that
    objects raises, and the exception leaves through here. The list is a
    leftover from when this collected them.)
    \"\"\"
    for field in schema['fields']:
        value = document.get(field['name'])
        for rule in field['rules']:
            rule(value, field['name'])
    return []""",
            new="""def validate(document, schema):
    \"\"\"Check a document against a schema.

    Returns every problem found, in form order, at most one per field: once a
    field has objected, the rules after it on the same field have nothing left
    to add and would only bury the first answer.
    \"\"\"
    problems = []
    for field in schema['fields']:
        value = document.get(field['name'])
        for rule in field['rules']:
            try:
                rule(value, field['name'])
            except ValidationError as problem:
                problems.append(problem)
                break
    return problems""",
            why=("The rules still raise. This is the only layer that changed, "
                 "and it changed by catching rather than by asking every rule "
                 "in the codebase to speak differently."),
        ),
        Fix(
            path="validator/schema.py",
            old="""\"\"\"Applying a list of rules to a document.""",
            new="""\"\"\"Applying a list of rules to a document.

`validate` collects; `assert_valid` raises the first. Two callers, two needs.""",
            why="",
        ),
        Fix(
            path="validator/schema.py",
            old="""    The HTTP layer calls this and turns a ValidationError into a 422 with the
    field name in it.
    \"\"\"
    validate(document, schema)
    return document""",
            new="""    The HTTP layer calls this and turns a ValidationError into a 422 with the
    field name in it. It has never been able to handle a list.
    \"\"\"
    problems = validate(document, schema)
    if problems:
        raise problems[0]
    return document""",
            why=("`validate` no longer raises, so the entry point that is "
                 "supposed to raise now has to do it itself. This is the edit "
                 "the ticket did not mention and the suite did."),
        ),
        Fix(
            path="validator/schema.py",
            old="""is the order problems should be reported in.
\"\"\"
""",
            new="""is the order problems should be reported in.
\"\"\"
from .rules import ValidationError
""",
            why="",
        ),
    ),
))


# ---------------------------------------------------------------------------
# eventbus — a list being edited while it is being walked
# ---------------------------------------------------------------------------

_BUS_INIT = r'''
"""eventbus: publish a thing, whoever cares hears about it."""
from .core import Bus
from .topics import matches

__all__ = ["Bus", "matches"]
'''

_BUS_TOPICS = r'''
"""Topic matching.

A topic is dot separated: "order.created", "order.line.added". A subscription
pattern may use "*" for exactly one segment and "#" for the rest of them.

    order.*      matches order.created, not order.line.added
    order.#      matches both
    #            matches everything
"""


def split(topic):
    return [part for part in topic.split('.') if part]


def matches(pattern, topic):
    """True if `topic` is one of the things `pattern` describes."""
    if pattern == topic:
        return True
    wanted = split(pattern)
    actual = split(topic)
    for index, part in enumerate(wanted):
        if part == '#':
            # Everything from here down, however deep. Only meaningful at the
            # end of a pattern, which nothing enforces.
            return True
        if index >= len(actual):
            return False
        if part != '*' and part != actual[index]:
            return False
    return len(wanted) == len(actual)


def is_wildcard(pattern):
    return '*' in pattern or '#' in pattern
'''

_BUS_CORE = r'''
"""The bus itself.

Handlers are called in the order they subscribed, which is not an accident:
the audit handler is registered first in production so that it sees an event
before anything downstream has had a chance to fall over.
"""
from .topics import matches


class Bus:

    def __init__(self):
        self._subscriptions = []
        self.delivered = 0
        self.dropped = 0

    def subscribe(self, pattern, handler):
        """Register a handler and hand it back, so this can be used as a
        decorator. Subscribing the same handler twice delivers to it twice."""
        self._subscriptions.append([pattern, handler])
        return handler

    def unsubscribe(self, handler):
        """Remove every subscription belonging to this handler."""
        for entry in list(self._subscriptions):
            if entry[1] is handler:
                self._subscriptions.remove(entry)

    def subscriptions(self):
        return [(pattern, handler) for pattern, handler in self._subscriptions]

    def publish(self, topic, payload=None):
        """Deliver to every matching handler. Returns how many were called."""
        count = 0
        for pattern, handler in self._subscriptions:
            if matches(pattern, topic):
                handler(topic, payload)
                count += 1
        self.delivered += count
        if count == 0:
            self.dropped += 1
        return count
'''

_BUS_TEST_TOPICS = r'''
"""Topic matching tests."""
from eventbus import matches


def test_an_exact_topic_matches_itself():
    assert matches('order.created', 'order.created') is True
    assert matches('order.created', 'order.deleted') is False


def test_a_star_matches_exactly_one_segment():
    assert matches('order.*', 'order.created') is True
    assert matches('order.*', 'order.line.added') is False
    assert matches('order.*', 'order') is False


def test_a_hash_matches_the_rest():
    assert matches('order.#', 'order.created') is True
    assert matches('order.#', 'order.line.added') is True
    assert matches('#', 'anything.at.all') is True


def test_a_different_prefix_never_matches():
    assert matches('order.#', 'invoice.created') is False
    assert matches('order.*', 'invoice.created') is False
'''

_BUS_TEST_CORE = r'''
"""Bus tests.

The last two are the ticket. A handler that removes itself after the first
event was swallowing the handler registered after it, and the one that got
swallowed in production was the one that writes to the audit log.
"""
from eventbus import Bus


def test_a_handler_hears_the_topics_it_asked_for():
    bus = Bus()
    heard = []
    bus.subscribe('order.*', lambda topic, payload: heard.append((topic, payload)))
    assert bus.publish('order.created', {'id': 1}) == 1
    assert bus.publish('invoice.created', {'id': 2}) == 0
    assert heard == [('order.created', {'id': 1})]


def test_handlers_run_in_the_order_they_subscribed():
    # The audit handler goes on first in production, deliberately, so that it
    # sees the event before anything downstream gets a chance to throw.
    bus = Bus()
    order = []
    for name in ('audit', 'email', 'metrics'):
        bus.subscribe('#', lambda topic, payload, n=name: order.append(n))
    bus.publish('order.created')
    assert order == ['audit', 'email', 'metrics']


def test_the_same_handler_subscribed_twice_is_called_twice():
    bus = Bus()
    seen = []

    def handler(topic, payload):
        seen.append(topic)
    bus.subscribe('order.*', handler)
    bus.subscribe('order.created', handler)
    assert bus.publish('order.created') == 2
    assert seen == ['order.created', 'order.created']


def test_unsubscribing_removes_every_subscription_of_that_handler():
    bus = Bus()

    def handler(topic, payload):
        raise AssertionError('should not be called')
    bus.subscribe('order.*', handler)
    bus.subscribe('#', handler)
    bus.unsubscribe(handler)
    assert bus.subscriptions() == []
    assert bus.publish('order.created') == 0


def test_events_nobody_wanted_are_counted():
    bus = Bus()
    bus.publish('order.created')
    bus.publish('order.created')
    assert bus.dropped == 2
    assert bus.delivered == 0


def test_a_handler_that_unsubscribes_itself_does_not_swallow_the_next_one():
    bus = Bus()
    seen = []

    def once(topic, payload):
        seen.append('once')
        bus.unsubscribe(once)

    def always(topic, payload):
        seen.append('always')
    bus.subscribe('order.*', once)
    bus.subscribe('order.*', always)
    assert bus.publish('order.created') == 2
    assert seen == ['once', 'always']
    seen[:] = []
    assert bus.publish('order.created') == 1
    assert seen == ['always']


def test_a_handler_removed_mid_dispatch_still_sees_the_event_in_flight():
    # The event was routed before anybody unsubscribed. Delivering it is the
    # honest outcome; the unsubscribe takes effect from the next one.
    bus = Bus()
    seen = []

    def first(topic, payload):
        seen.append('first')
        bus.unsubscribe(second)

    def second(topic, payload):
        seen.append('second')
    bus.subscribe('#', first)
    bus.subscribe('#', second)
    assert bus.publish('order.created') == 2
    assert seen == ['first', 'second']
    seen[:] = []
    assert bus.publish('order.created') == 1
    assert seen == ['first']
'''

register(Repo(
    id="eventbus",
    title="eventbus: the audit log that stopped",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="stack_queue_mines",
    tags=("iteration", "callbacks"),
    target_seconds=900,
    brief=(
        "A handler that removes itself after the first event was swallowing "
        "whatever was registered after it. In production the thing registered "
        "after it was the audit log, and nobody noticed for a week.\n\n"
        "A handler unsubscribing during a dispatch must not affect the "
        "handlers behind it: they still run, and they still run in order. The "
        "unsubscribe takes effect from the next event — the one in flight was "
        "already routed."
    ),
    start_file="eventbus/core.py",
    start_note=(
        "`publish` is nine lines. `unsubscribe` is four. Read them together "
        "and ask what happens to a `for` loop when the thing it is walking "
        "gets shorter underneath it."
    ),
    lesson=(
        "Removing from a list while iterating it does not raise; it silently "
        "skips. The fix is a snapshot, and it has to be a snapshot rather "
        "than anything that reorders or deduplicates: the order handlers run "
        "in is a documented promise with a test on it, and so is the fact "
        "that subscribing the same handler twice pages it twice."
    ),
    files={
        "eventbus/__init__.py": src(_BUS_INIT),
        "eventbus/topics.py": src(_BUS_TOPICS),
        "eventbus/core.py": src(_BUS_CORE),
    },
    tests={
        "tests/test_topics.py": src(_BUS_TEST_TOPICS),
        "tests/test_core.py": src(_BUS_TEST_CORE),
    },
    targets=(
        "tests/test_core.py::"
        "test_a_handler_that_unsubscribes_itself_does_not_swallow_the_next_one",
        "tests/test_core.py::"
        "test_a_handler_removed_mid_dispatch_still_sees_the_event_in_flight",
    ),
    patch=(
        Fix(
            path="eventbus/core.py",
            old="""        for pattern, handler in self._subscriptions:""",
            new="""        # A snapshot: a handler is allowed to subscribe or unsubscribe while
        # this loop is running, and neither may change who receives the event
        # that is already on its way.
        for pattern, handler in list(self._subscriptions):""",
            why=("A list copy rather than a set, because subscription order "
                 "is a promise the audit handler depends on."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# workflow — two generations of guard, and one that is not listened to
# ---------------------------------------------------------------------------

_WF_INIT = r'''
"""workflow: what may follow what."""
from .machine import Blocked, Machine
from .orders import ORDER_MACHINE, advance

__all__ = ["Machine", "Blocked", "ORDER_MACHINE", "advance"]
'''

_WF_MACHINE = r'''
"""A small state machine.

A transition is a dict: {"from": state, "event": name, "to": state} and
optionally "guard", a callable taking the context.

Guards come in two generations, because they were written a year apart and
nobody went back for the first lot:

  * the older ones return True to allow and False to refuse,
  * the newer ones return None to allow and a string explaining themselves.

_objection understands both and normalises them to "a reason, or None".
"""


class Blocked(Exception):
    def __init__(self, state, event, reason):
        super().__init__("%s cannot %s: %s" % (state, event, reason))
        self.state = state
        self.event = event
        self.reason = reason


class Machine:

    def __init__(self, transitions):
        self.transitions = list(transitions)

    def _find(self, state, event):
        for transition in self.transitions:
            if transition["from"] == state and transition["event"] == event:
                return transition
        return None

    def _objection(self, transition, context):
        """Ask the guard whether it objects. Returns a reason, or None."""
        guard = transition.get("guard")
        if guard is None:
            return None
        verdict = guard(context)
        if verdict is None or verdict is True:
            return None
        if isinstance(verdict, str):
            return verdict
        return None

    def can(self, state, event, context=None):
        """Whether `event` is allowed from `state` right now."""
        transition = self._find(state, event)
        if transition is None:
            return False
        return self._objection(transition, context or {}) is None

    def fire(self, state, event, context=None):
        """Take the transition and return the new state, or raise Blocked."""
        transition = self._find(state, event)
        if transition is None:
            raise Blocked(state, event, "there is no such transition")
        reason = self._objection(transition, context or {})
        if reason is not None:
            raise Blocked(state, event, reason)
        return transition["to"]

    def events_from(self, state):
        return sorted({t["event"] for t in self.transitions if t["from"] == state})
'''

_WF_ORDERS = r'''
"""The order workflow.

    placed -> picked -> shipped -> delivered

with a cancel available until it has shipped. The guards below are the two
generations the machine talks about: has_stock and not_already_shipped are the
new style and explain themselves, is_paid is one of the old ones.
"""
from .machine import Blocked, Machine


def has_stock(order):
    if order.get('stock', 0) < order.get('quantity', 1):
        return 'there is not enough stock'
    return None


def not_already_shipped(order):
    if order.get('shipped_at'):
        return 'it has already shipped'
    return None


def is_paid(order):
    return bool(order.get('paid'))


TRANSITIONS = [
    {'from': 'placed', 'event': 'pick', 'to': 'picked', 'guard': has_stock},
    {'from': 'picked', 'event': 'ship', 'to': 'shipped', 'guard': is_paid},
    {'from': 'shipped', 'event': 'deliver', 'to': 'delivered'},
    {'from': 'placed', 'event': 'cancel', 'to': 'cancelled',
     'guard': not_already_shipped},
    {'from': 'picked', 'event': 'cancel', 'to': 'cancelled',
     'guard': not_already_shipped},
]

ORDER_MACHINE = Machine(TRANSITIONS)


def advance(order, event):
    """Move an order on, in place, and return its new state."""
    order['state'] = ORDER_MACHINE.fire(order.get('state', 'placed'), event, order)
    return order['state']


def what_next(order):
    # The little grey buttons on the order page.
    return ORDER_MACHINE.events_from(order.get('state', 'placed'))
'''

_WF_TEST_MACHINE = r'''
"""Machine tests, on toy transitions rather than the real workflow."""
from workflow import Blocked, Machine

PLAIN = [{"from": "a", "event": "go", "to": "b"}]


def test_a_transition_with_no_guard_just_happens():
    machine = Machine(PLAIN)
    assert machine.can("a", "go") is True
    assert machine.fire("a", "go") == "b"


def test_an_event_that_does_not_exist_here_is_refused():
    machine = Machine(PLAIN)
    assert machine.can("b", "go") is False
    try:
        machine.fire("b", "go")
    except Blocked as exc:
        assert "no such transition" in exc.reason
        return
    raise AssertionError("there is no transition out of b")


def test_a_new_style_guard_returning_None_allows_it():
    machine = Machine([{"from": "a", "event": "go", "to": "b",
                        "guard": lambda ctx: None}])
    assert machine.can("a", "go", {}) is True
    assert machine.fire("a", "go", {}) == "b"


def test_a_new_style_guard_returning_a_string_blocks_with_that_reason():
    machine = Machine([{"from": "a", "event": "go", "to": "b",
                        "guard": lambda ctx: "the door is locked"}])
    assert machine.can("a", "go", {}) is False
    try:
        machine.fire("a", "go", {})
    except Blocked as exc:
        assert exc.reason == "the door is locked"
        return
    raise AssertionError("a guard that objects must block the transition")


def test_an_old_style_guard_returning_True_allows_it():
    machine = Machine([{"from": "a", "event": "go", "to": "b",
                        "guard": lambda ctx: True}])
    assert machine.can("a", "go", {}) is True
    assert machine.fire("a", "go", {}) == "b"


def test_events_from_a_state_are_listed_alphabetically():
    machine = Machine([{"from": "a", "event": "zip", "to": "b"},
                       {"from": "a", "event": "art", "to": "c"},
                       {"from": "b", "event": "go", "to": "c"}])
    assert machine.events_from("a") == ["art", "zip"]


def test_an_old_style_guard_returning_False_blocks():
    def is_ready(context):
        return bool(context.get("ready"))

    machine = Machine([{"from": "a", "event": "go", "to": "b",
                        "guard": is_ready}])
    assert machine.can("a", "go", {"ready": False}) is False
    try:
        machine.fire("a", "go", {"ready": False})
    except Blocked as exc:
        # The old guards do not explain themselves, so the machine has to.
        assert "is_ready" in exc.reason
    else:
        raise AssertionError("a guard that said False must block")
    assert machine.fire("a", "go", {"ready": True}) == "b"
'''

_WF_TEST_ORDERS = r'''
"""Order workflow tests.

The last one is the ticket. Two unpaid orders shipped on Tuesday.
"""
from workflow import Blocked
from workflow import orders

GOOD = {'state': 'placed', 'stock': 10, 'quantity': 1, 'paid': True}


def _order(**extra):
    order = dict(GOOD)
    order.update(extra)
    return order


def test_the_happy_path():
    order = _order()
    assert orders.advance(order, 'pick') == 'picked'
    assert orders.advance(order, 'ship') == 'shipped'
    assert orders.advance(order, 'deliver') == 'delivered'
    assert order['state'] == 'delivered'


def test_picking_without_stock_says_why():
    order = _order(stock=0)
    try:
        orders.advance(order, 'pick')
    except Blocked as exc:
        assert exc.reason == 'there is not enough stock'
        assert order['state'] == 'placed'
        return
    raise AssertionError('an order with no stock cannot be picked')


def test_a_shipped_order_cannot_be_cancelled():
    order = _order(state='picked', shipped_at='2024-04-01')
    try:
        orders.advance(order, 'cancel')
    except Blocked as exc:
        assert exc.reason == 'it has already shipped'
        return
    raise AssertionError('a shipped order cannot be cancelled')


def test_an_order_that_has_not_shipped_can_be_cancelled():
    order = _order()
    assert orders.advance(order, 'cancel') == 'cancelled'


def test_the_buttons_on_the_order_page():
    assert orders.what_next({'state': 'placed'}) == ['cancel', 'pick']
    assert orders.what_next({'state': 'shipped'}) == ['deliver']


def test_an_unpaid_order_does_not_ship():
    order = _order(state='picked', paid=False)
    try:
        orders.advance(order, 'ship')
    except Blocked as exc:
        assert 'is_paid' in exc.reason
        assert order['state'] == 'picked'
        return
    raise AssertionError('an unpaid order must not ship')
'''

register(Repo(
    id="workflow",
    title="workflow: two unpaid orders shipped on Tuesday",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="recursive_forest",
    tags=("state-machines", "truthiness"),
    target_seconds=1080,
    brief=(
        "Two unpaid orders shipped on Tuesday. The workflow has a guard on "
        "that transition and the guard said no.\n\n"
        "Make a refusal from the older generation of guard block the "
        "transition, with a reason naming the guard — those guards do not "
        "explain themselves, so the machine has to. The newer guards keep "
        "behaving exactly as they do now, and there are three of them in this "
        "repository alone."
    ),
    start_file="workflow/machine.py",
    start_note=(
        "`_objection` is the only place a guard is ever consulted, and it is "
        "eight lines. Read its docstring, then read every guard in orders.py, "
        "and work out which returns it actually accounts for."
    ),
    lesson=(
        "Three of the four possible returns are handled and the fourth falls "
        "off the end into `return None`, which is the word for `no "
        "objection`. The tempting repair — anything that is not True is a "
        "refusal — reads better and breaks every new-style guard in the "
        "codebase, all of which allow by returning None."
    ),
    files={
        "workflow/__init__.py": src(_WF_INIT),
        "workflow/machine.py": src(_WF_MACHINE),
        "workflow/orders.py": src(_WF_ORDERS),
    },
    tests={
        "tests/test_machine.py": src(_WF_TEST_MACHINE),
        "tests/test_orders.py": src(_WF_TEST_ORDERS),
    },
    targets=(
        "tests/test_machine.py::test_an_old_style_guard_returning_False_blocks",
        "tests/test_orders.py::test_an_unpaid_order_does_not_ship",
    ),
    patch=(
        Fix(
            path="workflow/machine.py",
            old="""        if isinstance(verdict, str):
            return verdict
        return None""",
            new="""        if isinstance(verdict, str):
            return verdict
        # Anything else is an old-style refusal. It has no reason of its own,
        # so it borrows the guard's name, which is the only useful thing we
        # know about it.
        return "blocked by %s" % getattr(guard, "__name__", "a guard")""",
            why=("The two allowing cases are still matched explicitly above, "
                 "so every new-style guard that returns None is untouched. "
                 "Only the fall-through changed meaning."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# pager — integer division, and the page that falls off the end
# ---------------------------------------------------------------------------

_PAGER_INIT = r'''
"""pager: cut a result set into pages people can click through."""
from .links import next_page, previous_page, summary, window
from .page import PageError, bounds, page_count, page_of, slice_of

__all__ = ["page_count", "bounds", "slice_of", "page_of", "PageError",
           "next_page", "previous_page", "window", "summary"]
'''

_PAGER_PAGE = r'''
"""Turning a result set into pages.

Pages are numbered from 1, because people read them. Item indices are counted
from 0, because people do not.
"""


class PageError(ValueError):
    """A page size or number that does not mean anything."""


def page_count(total, size):
    """How many pages `total` items make, at `size` items to a page."""
    if size < 1:
        raise PageError('a page holds at least one item')
    if total < 0:
        # Cannot happen. Totals arrive from len() or from COUNT(*).
        raise PageError('a negative number of items')
    return total // size


def bounds(number, size):
    """The (start, stop) slice for page `number`, pages counted from 1."""
    if number < 1:
        raise PageError('pages are numbered from 1')
    start = (number - 1) * size
    return start, start + size


def slice_of(items, number, size):
    start, stop = bounds(number, size)
    return items[start:stop]


def page_of(index, size):
    """Which page a 0-based item index lands on.

    The only caller is `jump to the thing you just created`, which has the
    index because it just inserted it.
    """
    return index // size + 1
'''

_PAGER_LINKS = r'''
"""The pagination widget.

Everything in here asks page.page_count how many pages there are, rather than
working it out again, so that the widget and the slice can never disagree.
"""
from .page import page_count


def next_page(current, total, size):
    """The next page number, or None when there is not one."""
    last = page_count(total, size)
    if current >= last:
        return None
    return current + 1


def previous_page(current, total, size):
    if current <= 1:
        return None
    return current - 1


def window(current, total, size, width=5):
    """Up to `width` page numbers centred on `current`, clamped to both ends."""
    last = page_count(total, size)
    if last < 1:
        return []
    half = width // 2
    start = max(1, current - half)
    stop = min(last, start + width - 1)
    start = max(1, stop - width + 1)
    return list(range(start, stop + 1))


def summary(current, total, size):
    """The line under the table: `Showing 11-20 of 57`."""
    if total == 0:
        return 'Nothing to show'
    first = (current - 1) * size + 1
    last = min(total, current * size)
    return 'Showing %d-%d of %d' % (first, last, total)
'''

_PAGER_TEST_PAGE = r'''
"""Paging tests.

The last one is the ticket: a search returning 7 results shows 6 of them and
the seventh cannot be reached by any link on the page.
"""
from pager import PageError, bounds, page_count, page_of, slice_of

ITEMS = list(range(1, 8))


def test_pages_of_an_exact_multiple():
    assert page_count(6, 3) == 2
    assert page_count(10, 10) == 1
    assert page_count(100, 10) == 10


def test_nothing_at_all_is_no_pages():
    # Not one empty page: the widget renders nothing rather than a lonely `1`.
    assert page_count(0, 3) == 0


def test_a_page_of_nothing_is_refused():
    for size in (0, -1):
        try:
            page_count(10, size)
        except PageError:
            continue
        raise AssertionError('size %r should be refused' % (size,))


def test_bounds_are_a_python_slice():
    assert bounds(1, 3) == (0, 3)
    assert bounds(3, 3) == (6, 9)
    try:
        bounds(0, 3)
    except PageError:
        pass
    else:
        raise AssertionError('page 0 does not exist')


def test_slicing_the_last_page_takes_what_is_there():
    assert slice_of(ITEMS, 3, 3) == [7]
    assert slice_of(ITEMS, 4, 3) == []


def test_page_of_an_item_index():
    assert page_of(0, 3) == 1
    assert page_of(2, 3) == 1
    assert page_of(3, 3) == 2


def test_a_partial_last_page_is_still_a_page():
    assert page_count(7, 3) == 3
    assert page_count(1, 10) == 1
    assert page_count(11, 10) == 2
'''

_PAGER_TEST_LINKS = r'''
"""Widget tests.

The last one is the other half of the ticket: whatever page_count says, these
are the links the reader actually gets to click.
"""
from pager import next_page, previous_page, summary, window


def test_next_and_previous_in_the_middle():
    assert next_page(2, 30, 10) == 3
    assert previous_page(2, 30, 10) == 1


def test_there_is_nothing_before_the_first_page():
    assert previous_page(1, 30, 10) is None


def test_there_is_nothing_after_the_last_page():
    assert next_page(3, 30, 10) is None


def test_the_window_clamps_to_the_start():
    assert window(1, 30, 3, width=5) == [1, 2, 3, 4, 5]


def test_the_window_clamps_to_the_end():
    assert window(9, 30, 3, width=5) == [6, 7, 8, 9, 10]


def test_an_empty_result_set_has_no_widget():
    assert window(1, 0, 10) == []
    assert summary(1, 0, 10) == 'Nothing to show'


def test_the_summary_counts_from_one():
    assert summary(2, 57, 10) == 'Showing 11-20 of 57'
    assert summary(6, 57, 10) == 'Showing 51-57 of 57'


def test_the_widget_offers_the_partial_last_page():
    assert next_page(2, 7, 3) == 3
    assert next_page(3, 7, 3) is None
    assert window(1, 7, 3) == [1, 2, 3]
'''

register(Repo(
    id="pager",
    title="pager: the seventh result nobody can reach",
    difficulty="EASY",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="fields_of_syntax",
    tags=("arithmetic", "off-by-one"),
    target_seconds=600,
    brief=(
        "A search returning seven results shows six of them. There is no link "
        "to the seventh and there never was.\n\n"
        "Fix the count. An empty result set must still produce no pages at "
        "all — the widget renders nothing rather than a lonely 1 — and every "
        "exact multiple must come out exactly as it does now."
    ),
    start_file="pager/page.py",
    start_note=(
        "One arithmetic expression is wrong and it is in the first function. "
        "The interesting part is the two existing tests either side of it that "
        "rule out the fix you will reach for first."
    ),
    lesson=(
        "`total // size + 1` fixes seven items and breaks both six items and "
        "none at all. Rounding a division up without inventing a page out of "
        "nothing is `-(-total // size)`, or `(total + size - 1) // size`, and "
        "both of those are worth being able to write without stopping."
    ),
    files={
        "pager/__init__.py": src(_PAGER_INIT),
        "pager/page.py": src(_PAGER_PAGE),
        "pager/links.py": src(_PAGER_LINKS),
    },
    tests={
        "tests/test_page.py": src(_PAGER_TEST_PAGE),
        "tests/test_links.py": src(_PAGER_TEST_LINKS),
    },
    targets=(
        "tests/test_page.py::test_a_partial_last_page_is_still_a_page",
        "tests/test_links.py::test_the_widget_offers_the_partial_last_page",
    ),
    patch=(
        Fix(
            path="pager/page.py",
            old="""        raise PageError('a negative number of items')
    return total // size""",
            new="""        raise PageError('a negative number of items')
    # Rounded up, without inventing a page when there is nothing at all:
    # -(-0 // 3) is 0, while 0 // 3 + 1 would be 1.
    return -(-total // size)""",
            why=("The widget gets it for free: every function in links.py asks "
                 "this one rather than dividing again."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# router — a rule written in the docstring and nowhere else
# ---------------------------------------------------------------------------

_ROUTER_INIT = r'''
"""router: turn a path into the thing that handles it."""
from .pattern import match, segments
from .table import Route, Router

__all__ = ["Router", "Route", "match", "segments"]
'''

_ROUTER_PATTERN = r'''
"""Compiling and matching one route pattern.

A pattern is a path with optional {placeholders} in it:

    /users              matches /users
    /users/{id}         matches /users/42, capturing {"id": "42"}
    /users/{id}/edit    matches /users/42/edit

A placeholder matches exactly one segment. It never matches across a slash and
never matches an empty one.
"""


def segments(path):
    """Split a path into segments. A trailing slash makes no difference."""
    return [part for part in path.split("/") if part]


def is_placeholder(segment):
    return segment.startswith("{") and segment.endswith("}")


def name_of(segment):
    return segment[1:-1]


def match(pattern, path):
    """The captured parameters, or None when the pattern does not match."""
    wanted = segments(pattern)
    actual = segments(path)
    if len(wanted) != len(actual):
        return None
    params = {}
    for want, have in zip(wanted, actual):
        if is_placeholder(want):
            if not have:
                # Cannot happen: segments() has already dropped the empties.
                return None
            params[name_of(want)] = have
        elif want != have:
            return None
    return params


def placeholder_names(pattern):
    # For the route table in the docs, which is generated nightly and read
    # roughly annually.
    return [name_of(s) for s in segments(pattern) if is_placeholder(s)]
'''

_ROUTER_TABLE = r'''
"""The routing table."""
from .pattern import is_placeholder, match, segments


class Route:

    def __init__(self, pattern, handler):
        self.pattern = pattern
        self.handler = handler
        self.segments = segments(pattern)

    def __repr__(self):
        return "<Route %s>" % self.pattern


class Router:

    def __init__(self):
        self.routes = []

    def add(self, pattern, handler):
        route = Route(pattern, handler)
        self.routes.append(route)
        return route

    def resolve(self, path):
        """Find the route for a path. Returns (handler, params), or None.

        The most specific pattern wins: a literal segment beats a placeholder
        at the first position where two candidates differ. Two patterns of
        equal specificity are resolved in the order they were registered.
        """
        for route in self.routes:
            params = match(route.pattern, path)
            if params is not None:
                return route.handler, params
        return None

    def patterns(self):
        return [route.pattern for route in self.routes]
'''

_ROUTER_TEST_PATTERN = r'''
"""Pattern tests: one pattern against one path, no table involved."""
from router import match
from router.pattern import placeholder_names, segments


def test_a_literal_path_matches_itself():
    assert match("/users", "/users") == {}
    assert match("/users", "/orders") is None


def test_a_trailing_slash_makes_no_difference():
    assert match("/users/", "/users") == {}
    assert match("/users", "/users/") == {}


def test_a_placeholder_captures_one_segment():
    assert match("/users/{id}", "/users/42") == {"id": "42"}
    assert match("/users/{id}", "/users/42/edit") is None
    assert match("/users/{id}", "/users") is None


def test_several_placeholders_capture_by_name():
    assert match("/users/{id}/posts/{slug}", "/users/7/posts/hello") == \
        {"id": "7", "slug": "hello"}


def test_segments_drops_the_empties():
    assert segments("//users//7/") == ["users", "7"]


def test_the_names_a_pattern_captures():
    assert placeholder_names("/users/{id}/posts/{slug}") == ["id", "slug"]
'''

_ROUTER_TEST_TABLE = r'''
"""Table tests.

The last one is the ticket. /users/me started returning somebody else's
profile the day the settings route was added, and the only thing that changed
was the order the routes are registered in.
"""
from router import Router


def show(request=None):
    return 'show'


def me(request=None):
    return 'me'


def edit(request=None):
    return 'edit'


def settings(request=None):
    return 'settings'


def test_a_path_with_no_route_resolves_to_nothing():
    router = Router()
    router.add('/users', show)
    assert router.resolve('/orders') is None


def test_a_matching_route_comes_back_with_its_parameters():
    router = Router()
    router.add('/users/{id}', show)
    handler, params = router.resolve('/users/42')
    assert handler is show
    assert params == {'id': '42'}


def test_two_equally_specific_patterns_go_in_registration_order():
    # Both of these match /things/1/2 and neither is more specific than the
    # other, so the one registered first is the one that wins. Reordering the
    # table must never be able to change this.
    router = Router()
    router.add('/things/{x}/{y}', show)
    router.add('/things/{a}/{b}', edit)
    handler, params = router.resolve('/things/1/2')
    assert handler is show
    assert params == {'x': '1', 'y': '2'}


def test_the_table_remembers_what_was_registered():
    router = Router()
    router.add('/users', show)
    router.add('/users/{id}', edit)
    assert router.patterns() == ['/users', '/users/{id}']


def test_a_literal_segment_beats_a_placeholder():
    router = Router()
    router.add('/users/{id}', show)
    router.add('/users/me', me)
    assert router.resolve('/users/me')[0] is me
    assert router.resolve('/users/42')[0] is show
    assert router.resolve('/users/42')[1] == {'id': '42'}


def test_specificity_is_decided_at_the_first_segment_that_differs():
    router = Router()
    router.add('/users/{id}/settings', settings)
    router.add('/users/me/{section}', edit)
    handler, params = router.resolve('/users/me/settings')
    assert handler is edit
    assert params == {'section': 'settings'}
'''

register(Repo(
    id="router",
    title="router: /users/me is somebody else",
    difficulty="MEDIUM",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="stringwood_labyrinth",
    tags=("matching", "ordering"),
    target_seconds=900,
    brief=(
        "/users/me started returning another customer's profile on the day the "
        "settings route was registered. Nothing about either route changed; "
        "only the order they are added in.\n\n"
        "The rule the table is supposed to follow is written down in "
        "Router.resolve and implemented nowhere. Implement it. Two patterns of "
        "equal specificity must still resolve in registration order, and there "
        "is a test that says so for a reason."
    ),
    start_file="router/table.py",
    start_note=(
        "Read the docstring of `resolve`, then read the four lines under it. "
        "They are describing two different programs."
    ),
    lesson=(
        "The fix is a scoring pass over every candidate instead of a return "
        "from the first one. Two things make it harder than it looks: the "
        "reflex proxy for specificity is pattern length, which gets "
        "/users/{id} versus /users/me exactly backwards, and whatever "
        "reordering you do has to keep registration order as the tie-break, "
        "which is the one guarantee that makes a routing table readable from "
        "top to bottom."
    ),
    files={
        "router/__init__.py": src(_ROUTER_INIT),
        "router/pattern.py": src(_ROUTER_PATTERN),
        "router/table.py": src(_ROUTER_TABLE),
    },
    tests={
        "tests/test_pattern.py": src(_ROUTER_TEST_PATTERN),
        "tests/test_table.py": src(_ROUTER_TEST_TABLE),
    },
    targets=(
        "tests/test_table.py::test_a_literal_segment_beats_a_placeholder",
        "tests/test_table.py::"
        "test_specificity_is_decided_at_the_first_segment_that_differs",
    ),
    patch=(
        Fix(
            path="router/table.py",
            old="""        for route in self.routes:
            params = match(route.pattern, path)
            if params is not None:
                return route.handler, params
        return None""",
            new="""        best = None
        for order, route in enumerate(self.routes):
            params = match(route.pattern, path)
            if params is None:
                continue
            # A literal scores above a placeholder, segment by segment, and
            # tuples compare left to right, which is exactly the documented
            # rule. Every candidate matched the same path, so every key is the
            # same length. `-order` keeps the earliest registration on top.
            key = (tuple(0 if is_placeholder(s) else 1 for s in route.segments),
                   -order)
            if best is None or key > best[0]:
                best = (key, route.handler, params)
        if best is None:
            return None
        return best[1], best[2]""",
            why=("Scored, not sorted. The table keeps its order and the "
                 "tie-break stays `whoever was registered first`."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# difftool — a presentation bug one layer below the presentation
# ---------------------------------------------------------------------------

_DIFF_INIT = r'''
"""difftool: what changed, and where."""
from .lcs import common, opcodes
from .render import unified

__all__ = ["common", "opcodes", "unified"]
'''

_DIFF_LCS = r'''
"""The shared spine of two sequences, and the edit script that follows.

Everything in this module is 0-based and half-open, like a Python slice,
because everything that calls it is Python. The one consumer that counts
differently is the unified renderer, and it converts at its own edge.
"""


def table(a, b):
    """The classic longest-common-subsequence length table."""
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            if a[i] == b[j]:
                rows[i][j] = rows[i + 1][j + 1] + 1
            else:
                rows[i][j] = max(rows[i + 1][j], rows[i][j + 1])
    return rows


def common(a, b):
    """Index pairs (i, j) of one longest common subsequence, in order."""
    rows = table(a, b)
    pairs = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif rows[i + 1][j] >= rows[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def opcodes(a, b):
    """The edit script: a list of (tag, i1, i2, j1, j2), 0-based, half-open.

    Tags are "equal", "delete", "insert" and "replace". Runs of equal lines
    are merged, so two equal opcodes never sit next to each other.
    """
    codes = []
    i = j = 0
    for ai, bj in common(a, b) + [(len(a), len(b))]:
        if ai > i and bj > j:
            codes.append(("replace", i, ai, j, bj))
        elif ai > i:
            codes.append(("delete", i, ai, j, bj))
        elif bj > j:
            codes.append(("insert", i, ai, j, bj))
        if ai < len(a) and bj < len(b):
            if codes and codes[-1][0] == "equal":
                tag, i1, i2, j1, j2 = codes[-1]
                codes[-1] = ("equal", i1, ai + 1, j1, bj + 1)
            else:
                codes.append(("equal", ai, ai + 1, bj, bj + 1))
        i, j = ai + 1, bj + 1
    return codes


def ratio(a, b):
    # Similarity, for the "these two files are basically the same" banner.
    total = len(a) + len(b)
    if not total:
        return 1.0
    return round(2.0 * len(common(a, b)) / total, 3)
'''

_DIFF_RENDER = r'''
"""Unified diff output.

A hunk header is `@@ -start,count +start,count @@`, and the review tool reads
the start out of it to decide which line to anchor a comment to.
"""
from .lcs import opcodes


def _groups(codes, context):
    """Break the edit script into hunks, trimming long runs of equal lines."""
    groups = []
    current = []
    for tag, i1, i2, j1, j2 in codes:
        if tag == "equal" and i2 - i1 > context * 2:
            if current:
                current.append(("equal", i1, min(i2, i1 + context),
                                j1, min(j2, j1 + context)))
                groups.append(current)
            current = [("equal", max(i1, i2 - context), i2,
                        max(j1, j2 - context), j2)]
            continue
        current.append((tag, i1, i2, j1, j2))
    if current and any(tag != "equal" for tag, _, _, _, _ in current):
        groups.append(current)
    return groups


def unified(old, new, context=1):
    """A unified diff of two lists of lines, as a list of output lines."""
    out = []
    for group in _groups(opcodes(old, new), context):
        old_start, old_stop = group[0][1], group[-1][2]
        new_start, new_stop = group[0][3], group[-1][4]
        out.append("@@ -%d,%d +%d,%d @@" % (old_start, old_stop - old_start,
                                            new_start, new_stop - new_start))
        for tag, a1, a2, b1, b2 in group:
            if tag == "equal":
                out.extend(" " + str(line) for line in old[a1:a2])
                continue
            if tag in ("replace", "delete"):
                out.extend("-" + str(line) for line in old[a1:a2])
            if tag in ("replace", "insert"):
                out.extend("+" + str(line) for line in new[b1:b2])
    return out


def changed_lines(old, new):
    # How many lines a review actually has to look at. The dashboard used to
    # show this next to the pull request title.
    return sum(code[2] - code[1] + code[4] - code[3]
               for code in opcodes(old, new) if code[0] != "equal")
'''

_DIFF_TEST_LCS = r'''
"""Edit script tests.

The indices here are 0-based and half-open on purpose: they index straight
into the lists, and three things in this package do exactly that.
"""
from difftool import common, opcodes
from difftool.lcs import ratio


def test_the_common_subsequence_of_two_identical_lists():
    assert common(["a", "b"], ["a", "b"]) == [(0, 0), (1, 1)]


def test_the_common_subsequence_skips_what_changed():
    assert common(["a", "b", "c"], ["a", "x", "c"]) == [(0, 0), (2, 2)]


def test_identical_input_is_one_equal_opcode():
    assert opcodes(["a", "b"], ["a", "b"]) == [("equal", 0, 2, 0, 2)]


def test_a_replacement_in_the_middle():
    assert opcodes(["a", "b", "c"], ["a", "x", "c"]) == [
        ("equal", 0, 1, 0, 1),
        ("replace", 1, 2, 1, 2),
        ("equal", 2, 3, 2, 3),
    ]


def test_an_insertion_indexes_into_the_new_list():
    assert opcodes(["a", "c"], ["a", "b", "c"]) == [
        ("equal", 0, 1, 0, 1),
        ("insert", 1, 1, 1, 2),
        ("equal", 1, 2, 2, 3),
    ]


def test_a_deletion_indexes_into_the_old_list():
    assert opcodes(["a", "b", "c"], ["a", "c"]) == [
        ("equal", 0, 1, 0, 1),
        ("delete", 1, 2, 1, 1),
        ("equal", 2, 3, 1, 2),
    ]


def test_ratio_is_one_for_identical_input():
    assert ratio(["a", "b"], ["a", "b"]) == 1.0
    assert ratio([], []) == 1.0
'''

_DIFF_TEST_RENDER = r'''
"""Renderer tests.

The last one is the ticket. Review comments have been landing one line above
the line they were written on since the tool was written, and the reviewers
have simply been correcting for it by eye.
"""
from difftool import unified
from difftool.render import changed_lines

OLD = ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]
NEW = ["L0", "L1", "X", "L3", "L4", "L5", "L6", "Y", "L8", "L9"]


def test_identical_input_produces_no_output_at_all():
    assert unified(["a", "b"], ["a", "b"]) == []


def test_a_replacement_is_shown_with_context():
    out = unified(["a", "b", "c", "d"], ["a", "B", "c", "d"], context=1)
    assert out[1:] == [" a", "-b", "+B", " c", " d"]


def test_an_insertion_is_shown_as_an_added_line():
    out = unified(["a", "c"], ["a", "b", "c"], context=1)
    assert out[1:] == [" a", "+b", " c"]


def test_a_deletion_is_shown_as_a_removed_line():
    out = unified(["a", "b", "c"], ["a", "c"], context=1)
    assert out[1:] == [" a", "-b", " c"]


def test_distant_changes_become_separate_hunks():
    out = unified(OLD, NEW, context=1)
    assert len([line for line in out if line.startswith("@@")]) == 2
    assert len(out) == 12


def test_changed_lines_counts_both_sides():
    assert changed_lines(["a", "b", "c"], ["a", "x", "c"]) == 2
    assert changed_lines(["a"], ["a"]) == 0


def test_hunk_headers_count_from_one():
    # The review tool reads the start out of the header and anchors the
    # comment there. Every other diff tool on earth counts the first line of a
    # file as line 1.
    out = unified(OLD, NEW, context=1)
    headers = [line for line in out if line.startswith("@@")]
    assert headers == ["@@ -1,4 +1,4 @@", "@@ -7,4 +7,4 @@"]
    small = unified(["a", "b", "c", "d"], ["a", "B", "c", "d"], context=1)
    assert small[0] == "@@ -1,4 +1,4 @@"
'''

register(Repo(
    id="difftool",
    title="difftool: every comment one line too high",
    difficulty="HARD",
    shapes=("FIX_BUG", "PRESERVE_CONTRACT"),
    realm="array_caverns",
    tags=("indices", "layering"),
    target_seconds=1500,
    brief=(
        "The review tool anchors a comment to the line named in the hunk "
        "header. Every comment lands one line above where it was written, and "
        "the reviewers have been correcting for it by eye for so long that "
        "nobody filed it.\n\n"
        "Hunk headers count a file's first line as line 1. Everything under "
        "the renderer is 0-based and indexes straight into the lists, which is "
        "correct and is tested six times."
    ),
    start_file="difftool/render.py",
    start_note=(
        "You do not need to understand the LCS to fix this. Read the module "
        "docstring in lcs.py, read the one line in render.py that builds the "
        "`@@` header, and work out which of the two is allowed to change."
    ),
    lesson=(
        "The defect is one number and the interesting question is which layer "
        "owns it. Shifting the opcodes is fewer keystrokes and breaks every "
        "index in the package, because those indices are used to slice the "
        "lists. A base-1 header is a fact about diff format, so it is the "
        "formatter's problem, and it converts at its own edge."
    ),
    files={
        "difftool/__init__.py": src(_DIFF_INIT),
        "difftool/lcs.py": src(_DIFF_LCS),
        "difftool/render.py": src(_DIFF_RENDER),
    },
    tests={
        "tests/test_lcs.py": src(_DIFF_TEST_LCS),
        "tests/test_render.py": src(_DIFF_TEST_RENDER),
    },
    targets=("tests/test_render.py::test_hunk_headers_count_from_one",),
    patch=(
        Fix(
            path="difftool/render.py",
            old="""def unified(old, new, context=1):""",
            new="""def _start(index, count):
    \"\"\"A 0-based index as a diff header start line.

    Diff counts a file's first line as 1. The special case is a hunk that is
    empty on one side: there is no line to point at, so the format points at
    the line it comes after, which is the 0-based index unchanged.
    \"\"\"
    return index + 1 if count else index


def unified(old, new, context=1):""",
            why="",
        ),
        Fix(
            path="difftool/render.py",
            old="""        out.append("@@ -%d,%d +%d,%d @@" % (old_start, old_stop - old_start,
                                            new_start, new_stop - new_start))""",
            new="""        old_count, new_count = old_stop - old_start, new_stop - new_start
        out.append("@@ -%d,%d +%d,%d @@" % (_start(old_start, old_count),
                                            old_count,
                                            _start(new_start, new_count),
                                            new_count))""",
            why=("Converted in the formatter, at the edge where the output "
                 "stops being Python indices and starts being diff. lcs.py "
                 "does not move."),
        ),
    ),
))


# ---------------------------------------------------------------------------
# dispatch — the big one: a rota, an escalation policy, and a pager
# ---------------------------------------------------------------------------

_DISPATCH_INIT = r'''
"""dispatch: work out who to wake up, then wake them up."""
from .notify import send
from .policy import escalation
from .rota import WEEK, covers, on_call

__all__ = ["on_call", "covers", "WEEK", "escalation", "send"]
'''

_DISPATCH_ROTA = r'''
"""Who is scheduled.

A shift is {"who": name, "start": minute, "end": minute} on a repeating weekly
clock measured in minutes from Monday 00:00. Shifts are half-open: [start, end)
covers start and does not cover end, so two shifts that touch never both claim
the handover minute.
"""

WEEK = 7 * 24 * 60
DAY = 24 * 60


def normalise(minute):
    """Any minute, mapped onto the week."""
    return minute % WEEK


def covers(shift, minute):
    """Whether `shift` covers `minute`."""
    start, end = shift["start"], shift["end"]
    minute = normalise(minute)
    if start <= end:
        return start <= minute <= end
    # A shift that runs past Sunday midnight and out the other side.
    return minute >= start or minute <= end


def on_call(shifts, minute):
    """The name scheduled at `minute`, or None if nobody is.

    The first matching shift wins. Overrides are prepended to the list, so a
    one-off cover shift beats the standing rota without anybody having to edit
    the standing rota.
    """
    for shift in shifts:
        if covers(shift, minute):
            return shift["who"]
    return None


def handovers(shifts):
    # For the calendar view, which draws a line at every change of hands.
    return sorted({normalise(s["start"]) for s in shifts})
'''

_DISPATCH_POLICY = r'''
"""Escalation.

A policy is a list of levels, in the order they are tried, each one saying how
long to wait before giving up and moving on:

    {'kind': 'oncall', 'rota': 'primary', 'after': 0}
    {'kind': 'oncall', 'rota': 'secondary', 'after': 15}
    {'kind': 'person', 'who': 'duty manager', 'after': 45}

A 'person' level names a human directly. It is the last resort and it is the
reason an alarm can never end up with nobody to send it to, so every policy in
production ends with one.
"""
from .rota import on_call


def available(people, who):
    """Whether somebody has said they can be woken up.

    Absence from `people` means yes. Most of the company is not in that dict
    and most of the company is not on call either.
    """
    return people.get(who, {}).get('available', True)


def escalation(policy, rotas, minute, people=None):
    """The people to try, in order, for an alarm raised at `minute`.

    Levels are tried in the order they are listed, which is assumed to be
    ascending by 'after'.
    """
    people = people or {}
    chain = []
    for level in policy:
        if level.get('kind') == 'person':
            who = level['who']
        else:
            who = on_call(rotas.get(level.get('rota'), []), minute)
        if who is None:
            continue
        chain.append({'who': who, 'after': level.get('after', 0),
                      'kind': level.get('kind', 'oncall')})
    return chain


def waiting_time(chain):
    # The alarm page shows this as "nobody has acknowledged for N minutes".
    return max([step['after'] for step in chain], default=0)
'''

_DISPATCH_NOTIFY = r'''
"""Sending the page.

This module has no opinions. It is handed a list of names and it delivers to
them; deciding who deserves to be woken up happens one layer up, in policy,
where the rota and the availability are. The only thing it does on its own
initiative is refuse to page the same person twice for the same incident.
"""

DEFAULT_CHANNEL = 'sms'


def send(targets, channels, sink, quiet_hours=False):
    """Deliver one message per person, in order, skipping repeats.

    `channels` is {name: channel}; anybody not in it gets DEFAULT_CHANNEL.
    `sink` is a list the messages are appended to. Returns how many went out.
    """
    seen = []
    for who in targets:
        if who in seen:
            continue
        seen.append(who)
        channel = channels.get(who, DEFAULT_CHANNEL)
        sink.append({'who': who, 'channel': channel})
    return len(seen)


def summarise(sink):
    return ', '.join('%s by %s' % (m['who'], m['channel']) for m in sink)
'''

_DISPATCH_TEST_ROTA = r'''
"""Rota tests.

The last one is the first ticket. At 09:00 on a Tuesday the alarm goes to
whoever was on call on Monday, for exactly one minute, and that minute is when
the deploy runs.
"""
from dispatch import WEEK, covers, on_call
from dispatch.rota import DAY, handovers

STANDING = [
    {"who": "ana", "start": 0, "end": DAY},
    {"who": "ben", "start": DAY, "end": 2 * DAY},
]


def test_the_middle_of_a_shift():
    assert on_call(STANDING, 60) == "ana"
    assert on_call(STANDING, DAY + 60) == "ben"


def test_the_minute_before_a_handover_belongs_to_the_outgoing_shift():
    assert on_call(STANDING, DAY - 1) == "ana"


def test_nobody_is_scheduled_outside_the_rota():
    assert on_call(STANDING, 3 * DAY) is None


def test_an_override_beats_the_standing_rota():
    # Overrides go on the front of the list. Nobody edits the standing rota to
    # cover a dentist appointment.
    shifts = [{"who": "cat", "start": 120, "end": 240}] + STANDING
    assert on_call(shifts, 180) == "cat"
    assert on_call(shifts, 300) == "ana"


def test_a_shift_may_run_out_of_one_week_and_into_the_next():
    wrap = {"who": "dev", "start": WEEK - 60, "end": 60}
    assert covers(wrap, WEEK - 30) is True
    assert covers(wrap, 30) is True
    assert covers(wrap, 5000) is False


def test_the_calendar_draws_a_line_at_every_handover():
    assert handovers(STANDING) == [0, DAY]


def test_the_handover_minute_belongs_to_the_incoming_shift():
    # Shifts are half-open. The minute a shift ends is the first minute of the
    # next one, and the outgoing person has gone to bed.
    assert on_call(STANDING, DAY) == "ben"
    assert covers(STANDING[0], DAY) is False
    assert covers(STANDING[1], DAY) is True
    wrap = {"who": "dev", "start": WEEK - 60, "end": 60}
    assert covers(wrap, 60) is False
'''

_DISPATCH_TEST_POLICY = r'''
"""Escalation tests.

The last one is the second ticket. Somebody marked themselves unavailable, the
alarm went to them anyway, and it sat unacknowledged for forty-five minutes
until the policy ran out of levels.
"""
from dispatch import escalation
from dispatch.policy import available, waiting_time
from dispatch.rota import DAY

ROTAS = {
    'primary': [{'who': 'ana', 'start': 0, 'end': DAY}],
    'secondary': [{'who': 'ben', 'start': 0, 'end': DAY}],
}

POLICY = [
    {'kind': 'oncall', 'rota': 'primary', 'after': 0},
    {'kind': 'oncall', 'rota': 'secondary', 'after': 15},
    {'kind': 'person', 'who': 'duty manager', 'after': 45},
]


def test_the_chain_is_primary_then_secondary_then_a_human():
    chain = escalation(POLICY, ROTAS, 60)
    assert [step['who'] for step in chain] == ['ana', 'ben', 'duty manager']
    assert [step['after'] for step in chain] == [0, 15, 45]


def test_a_rota_with_nobody_on_it_is_skipped():
    chain = escalation(POLICY, {'primary': ROTAS['primary']}, 60)
    assert [step['who'] for step in chain] == ['ana', 'duty manager']


def test_every_policy_ends_with_somebody_who_can_be_reached():
    # The last resort is why an alarm can never come out with nobody on it.
    chain = escalation(POLICY, {}, 60)
    assert [step['who'] for step in chain] == ['duty manager']
    assert chain[0]['kind'] == 'person'


def test_available_defaults_to_yes():
    assert available({}, 'ana') is True
    assert available({'ana': {'available': False}}, 'ana') is False


def test_the_waiting_time_is_the_last_level():
    assert waiting_time(escalation(POLICY, ROTAS, 60)) == 45


def test_somebody_unavailable_is_skipped_but_the_last_resort_never_is():
    people = {'ana': {'available': False}, 'duty manager': {'available': False}}
    chain = escalation(POLICY, ROTAS, 60, people)
    # ana has said she cannot be woken up, so the alarm starts at ben. The
    # duty manager does not get that privilege: the last resort is the reason
    # an alarm always reaches a human, and it is paged regardless.
    assert [step['who'] for step in chain] == ['ben', 'duty manager']
'''

_DISPATCH_TEST_NOTIFY = r'''
"""Delivery tests. This layer is not allowed to have opinions."""
from dispatch import send
from dispatch.notify import DEFAULT_CHANNEL, summarise

CHANNELS = {'ana': 'push', 'ben': 'phone'}


def test_one_message_per_person_in_order():
    sink = []
    assert send(['ana', 'ben'], CHANNELS, sink) == 2
    assert [m['who'] for m in sink] == ['ana', 'ben']
    assert [m['channel'] for m in sink] == ['push', 'phone']


def test_somebody_unknown_gets_the_default_channel():
    sink = []
    send(['zoe'], CHANNELS, sink)
    assert sink[0]['channel'] == DEFAULT_CHANNEL


def test_the_same_person_twice_is_one_page():
    sink = []
    assert send(['ana', 'ben', 'ana'], CHANNELS, sink) == 2
    assert [m['who'] for m in sink] == ['ana', 'ben']


def test_send_does_not_second_guess_the_list_it_was_given():
    # A manual page names a person on purpose, including people the policy
    # would have skipped. This layer delivers; policy decides.
    sink = []
    assert send(['ana'], CHANNELS, sink) == 1
    assert sink == [{'who': 'ana', 'channel': 'push'}]


def test_the_summary_line():
    sink = []
    send(['ana', 'zoe'], CHANNELS, sink)
    assert summarise(sink) == 'ana by push, zoe by sms'
'''

register(Repo(
    id="dispatch",
    title="dispatch: the minute nobody was on call",
    difficulty="ELITE",
    shapes=("FIX_BUG", "ADD_FEATURE", "PRESERVE_CONTRACT"),
    realm="null_kings_castle",
    tags=("time", "policy", "layering"),
    target_seconds=1800,
    brief=(
        "Two tickets from the same incident review.\n\n"
        "1. At the exact minute a shift changes hands, the alarm goes to the "
        "person who has just gone to bed. Shifts are documented as half-open "
        "and are not implemented that way.\n\n"
        "2. Somebody marked themselves unavailable. The alarm went to them "
        "anyway and sat there for forty-five minutes. Escalation must skip "
        "anyone who is unavailable — with one exception, and the incident "
        "review was very clear that the exception stays."
    ),
    start_file="dispatch/rota.py",
    start_note=(
        "Three modules, in a deliberate order: rota says who is scheduled, "
        "policy decides who is worth waking, notify delivers and has no "
        "opinions at all. Both tickets live in the first two. Neither belongs "
        "in the third, and the third has a test that says so."
    ),
    lesson=(
        "Both defects are one line, and both of them are really about which "
        "layer is allowed to know what. The rota reports the schedule; it does "
        "not know about availability and must not learn. Availability is a "
        "policy question, and policy is also where the exception lives — the "
        "last resort is paged whatever it says, because a chain with nobody in "
        "it is worse than waking somebody who asked not to be woken."
    ),
    files={
        "dispatch/__init__.py": src(_DISPATCH_INIT),
        "dispatch/rota.py": src(_DISPATCH_ROTA),
        "dispatch/policy.py": src(_DISPATCH_POLICY),
        "dispatch/notify.py": src(_DISPATCH_NOTIFY),
    },
    tests={
        "tests/test_rota.py": src(_DISPATCH_TEST_ROTA),
        "tests/test_policy.py": src(_DISPATCH_TEST_POLICY),
        "tests/test_notify.py": src(_DISPATCH_TEST_NOTIFY),
    },
    targets=(
        "tests/test_rota.py::test_the_handover_minute_belongs_to_the_incoming_shift",
        "tests/test_policy.py::"
        "test_somebody_unavailable_is_skipped_but_the_last_resort_never_is",
    ),
    patch=(
        Fix(
            path="dispatch/rota.py",
            old="""    if start <= end:
        return start <= minute <= end
    # A shift that runs past Sunday midnight and out the other side.
    return minute >= start or minute <= end""",
            new="""    if start <= end:
        return start <= minute < end
    # A shift that runs past Sunday midnight and out the other side.
    return minute >= start or minute < end""",
            why=("Half-open, as documented, on both branches. The wrapping "
                 "case is easy to fix on the ordinary branch alone and then "
                 "be wrong once a week."),
        ),
        Fix(
            path="dispatch/policy.py",
            old="""        if who is None:
            continue
        chain.append({'who': who, 'after': level.get('after', 0),""",
            new="""        if who is None:
            continue
        # Somebody who has said they cannot be woken up is skipped - except at
        # a 'person' level. That level is the last resort, and an alarm with
        # nobody on it is worse than waking somebody who asked not to be.
        if level.get('kind') != 'person' and not available(people, who):
            continue
        chain.append({'who': who, 'after': level.get('after', 0),""",
            why=("In policy, which is the layer that is allowed to have an "
                 "opinion about who deserves waking. Not in the rota, which "
                 "reports the schedule, and not in notify, which delivers."),
        ),
    ),
))


# ===========================================================================
# CONTRACT — what engine.py and server.py need from this module
# ===========================================================================
#
# This module owns the repositories and the rules. It owns no state, touches no
# database, imports nothing from the engine, and decides nothing about who may
# fight or what a win is worth. Six calls, in the order an encounter uses them.
#
#   1. CHOOSE
#        minirepo.catalogue(difficulty=..., tag=...) -> [index card, ...]
#        minirepo.pick(difficulty=..., exclude=cleared_ids, seed=...) -> Repo
#      `pick` never returns None while any repo exists; it widens the tier
#      rather than dead-ending. Difficulties are EASY, MEDIUM, HARD, ELITE.
#
#   2. OPEN
#        view = minirepo.player_view(repo, mode=enc.mode, sealed=sealed_caps)
#      where sealed_caps is built at the call site, one line per capability:
#
#        sealed_caps = {cap for cap in minirepo.SEALED_CAPABILITIES
#                       if finalexam.sealed(enc, cap)}
#
#      That is the only way this module learns what is sealed, and
#      `finalexam.sealed` stays the only place anything asks. Interview Mode
#      is additionally forced inside `player_view`, belt and braces, exactly
#      as `Problem.player_view(mode="interview")` does.
#
#      The view carries every file body, the test bodies marked
#      `editable: False`, and `target_seconds` for the clock. It never carries
#      the patch, in any mode, at any time.
#
#   3. CLOCK
#        repo.clock                      -> seconds this repo is worth
#      Use it the way `finalexam.clock_for` uses `problem.target_seconds`: the
#      repo's own number, with no BUILD grace, once the clock rung is reached.
#
#   4. RUN (the player pressing Run, mid-fight — optional, ungraded)
#        report = minirepo.run(repo, minirepo.assemble(repo, submitted))
#      Returns a sandbox.ExecutionReport. Show it; do not score it. Note that
#      `assemble` overwrites the test paths from the repo, so Run cannot be
#      used to find out what a weakened test would say.
#
#   5. GRADE
#        verdict = minirepo.grade(repo, submitted, seconds=elapsed)
#        rank    = minirepo.rank_for(repo, verdict, seconds=elapsed,
#                                    hints_used=n, first_try=bool)
#      `submitted` is {path: source} for the player's whole working tree.
#      Pass `full_tree=False` if it is a partial save, or every unsent test
#      reads as a deletion. `verdict.to_dict()` is JSON-ready.
#
#      Mastery moves on `verdict.solved` and nothing else. TAMPERED, BROKEN,
#      REGRESSED and INCOMPLETE are all `solved=False`; they differ in what
#      the player is told, not in what was earned.
#
#   6. DEBRIEF (after the attempt is scored)
#        minirepo.debrief(repo, verdict, sealed=sealed_caps)
#      Always returns the lesson and which file the cause lived in, including
#      after a tampered attempt — learning does not dead-end, even there. The
#      reference patch appears in `solution` only when SOLUTION is not sealed,
#      which is the same rule the worked solution follows everywhere else.
#
# WHAT THE WIRING AGENT MUST ADD ELSEWHERE
#
#   * "MINI_REPO" is not in corpus.schema.ENCOUNTER_KINDS. A Mini-Repo is not
#     a Problem — it has no single entry point, no reference callable and no
#     derived tests — so it should not be forced into one. If the encounter
#     table wants the string, add `minirepo.ENCOUNTER_KIND` to that list; do
#     not add Repos to the corpus.
#   * The client needs a read-only editor state for the test files. The server
#     already cannot be fooled (see `assemble`), so this is honesty in the
#     interface, not security.
#
# SELF-CHECK
#
#   minirepo.self_check() -> {"repos", "ok", "failed", "rows"}
#   minirepo.audit(repo)  -> one row: size and byte limits, stdlib-only,
#                            the patch applies, every target fails before,
#                            every other test passes before, the patch turns
#                            the whole suite green, and both cheats — editing
#                            a test and deleting one — are caught.
#   It runs the sandbox. That is the point: a Mini-Repo is only winnable if
#   something has actually won it.
