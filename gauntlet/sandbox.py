"""Safe local execution of player-written Python.

Layers of containment, outermost first:

1. ``sandbox-exec`` seatbelt profile (macOS): denies all network, denies writes
   outside the scratch directory. Verified at import time; if the binary is
   missing we degrade to layers 2-4 and report ``hardened=False``.
2. POSIX resource limits: CPU seconds, address space, file size, process count.
3. A wall-clock kill switch on the parent side.
4. Per-test SIGALRM timers inside the harness.

The child is launched with ``-I -S`` (isolated: no user site-packages, no
``PYTHONPATH``, no ``sitecustomize``) and a scrubbed environment.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import config

HARNESS = Path(__file__).resolve().parent / "_harness.py"
SANDBOX_EXEC = shutil.which("sandbox-exec")

_SEATBELT = """(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow sysctl-read)
(allow signal (target self))
(allow file-read-metadata)
(allow file-read*)
(allow file-write* (subpath "{scratch}"))
(allow file-write-data (literal "/dev/null"))
(deny network*)
(deny file-write* (subpath "{home}"))
"""

# Interpreter warnings that are noise from the seatbelt, not the player's fault.
_NOISE = ("confstr() failed", "DARWIN_USER_TEMP_DIR", "Python runtime state")


@dataclass
class TestResult:
    index: int
    name: str
    hidden: bool
    kind: str
    status: str          # pass | fail | timeout | exception
    ms: float
    message: str = ""
    got: Any = None
    expected: Any = None
    reveal: bool = True

    @property
    def passed(self) -> bool:
        return self.status == "pass"


@dataclass
class ExecutionReport:
    ok: bool
    phase: str                       # syntax | toplevel | tests | infra
    tests: list[TestResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: dict | None = None
    wall_ms: float = 0.0
    hardened: bool = True

    @property
    def passed_count(self) -> int:
        return sum(1 for t in self.tests if t.passed)

    @property
    def total_count(self) -> int:
        return len(self.tests)

    @property
    def all_passed(self) -> bool:
        return self.ok and bool(self.tests) and self.passed_count == self.total_count

    @property
    def slowest_ms(self) -> float:
        return max((t.ms for t in self.tests), default=0.0)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "phase": self.phase,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "wall_ms": round(self.wall_ms, 2),
            "hardened": self.hardened,
            "passed": self.passed_count,
            "total": self.total_count,
            "all_passed": self.all_passed,
            "tests": [
                {
                    "index": t.index, "name": t.name, "hidden": t.hidden,
                    "kind": t.kind, "status": t.status, "ms": t.ms,
                    "message": t.message, "got": t.got, "expected": t.expected,
                    "reveal": t.reveal,
                }
                for t in self.tests
            ],
        }


def _preexec(cpu: int, mem_mb: int):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (8 << 20, 8 << 20))
        try:
            soft = mem_mb << 20
            resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
        except (ValueError, OSError):
            pass  # macOS occasionally refuses RLIMIT_AS; CPU + wall clock still bound us
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass
        os.setsid()
    return apply


def _child_python() -> str:
    """Prefer the interpreter running the server; fall back to the system one."""
    return sys.executable or "/usr/bin/python3"


def _clean_stderr(raw: str) -> str:
    keep = [ln for ln in raw.splitlines() if not any(n in ln for n in _NOISE)]
    return "\n".join(keep).strip()


def run_tests(
    source: str,
    entry: dict,
    tests: list[dict],
    *,
    timeout_ms: int | None = None,
    wall_seconds: int | None = None,
    cpu_seconds: int | None = None,
    memory_mb: int | None = None,
) -> ExecutionReport:
    """Execute ``source`` against ``tests`` and return a structured report."""
    timeout_ms = timeout_ms or config.PER_TEST_TIMEOUT_MS
    wall_seconds = wall_seconds or config.SANDBOX_WALL_SECONDS
    cpu_seconds = cpu_seconds or config.SANDBOX_CPU_SECONDS
    memory_mb = memory_mb or config.SANDBOX_MEMORY_MB

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="gauntlet-run-") as scratch_str:
        # seatbelt subpath rules match the *physical* path (/private/var/...),
        # not the /var symlink that tempfile hands back.
        scratch = Path(os.path.realpath(scratch_str))
        payload_path = scratch / "payload.json"
        result_path = scratch / "result.json"
        harness_path = scratch / "harness.py"
        shutil.copyfile(HARNESS, harness_path)
        payload_path.write_text(json.dumps({
            "source": source,
            "entry": entry,
            "tests": tests,
            "timeout_ms": timeout_ms,
        }))

        argv = [_child_python(), "-I", "-S", "-B", str(harness_path),
                str(payload_path), str(result_path)]
        hardened = False
        if SANDBOX_EXEC and sys.platform == "darwin":
            profile = scratch / "profile.sb"
            profile.write_text(_SEATBELT.format(
                scratch=scratch, home=os.path.realpath(Path.home())))
            argv = [SANDBOX_EXEC, "-f", str(profile)] + argv
            hardened = True

        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(scratch),
            "TMPDIR": str(scratch),
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }

        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=wall_seconds,
                cwd=str(scratch), env=env, preexec_fn=_preexec(cpu_seconds, memory_mb),
                check=False,
            )
            stdout, stderr, killed = proc.stdout, proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", "replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", "replace")
            killed = True

        wall_ms = (time.perf_counter() - started) * 1000.0
        stdout = stdout[-20000:]
        stderr = _clean_stderr(stderr)[-8000:]

        if killed:
            return ExecutionReport(
                ok=False, phase="toplevel", stdout=stdout, stderr=stderr,
                wall_ms=wall_ms, hardened=hardened,
                error={"type": "Timeout",
                       "message": "your code ran for more than %ds and was stopped"
                                  % wall_seconds},
            )

        if not result_path.exists():
            detail = stderr or "the interpreter exited before producing results"
            if "MemoryError" in stderr or "Killed" in stderr:
                detail = "your code exceeded the %dMB memory limit" % memory_mb
            return ExecutionReport(
                ok=False, phase="infra", stdout=stdout, stderr=stderr,
                wall_ms=wall_ms, hardened=hardened,
                error={"type": "ExecutionAborted", "message": detail},
            )

        raw = json.loads(result_path.read_text())

    tests_out = [
        TestResult(
            index=t["index"], name=t["name"], hidden=t["hidden"], kind=t["kind"],
            status=t["status"], ms=t["ms"], message=t.get("message", ""),
            got=t.get("got"), expected=t.get("expected"), reveal=t.get("reveal", True),
        )
        for t in raw.get("tests", [])
    ]
    return ExecutionReport(
        ok=raw.get("ok", False), phase=raw.get("phase", "tests"), tests=tests_out,
        stdout=stdout, stderr=stderr, error=raw.get("error"),
        wall_ms=wall_ms, hardened=hardened,
    )


def run_scratch(source: str, *, wall_seconds: int = 8) -> ExecutionReport:
    """`Run` button: execute the file for its side effects, no grading."""
    return run_tests(source, {"kind": "function", "name": "__none__"}, [],
                     wall_seconds=wall_seconds)


def self_check() -> dict:
    """Verified at server boot and by the acceptance tests."""
    net = run_tests(
        "import socket\n"
        "def probe():\n"
        "    try:\n"
        "        socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "        return 'OPEN'\n"
        "    except Exception:\n"
        "        return 'BLOCKED'\n",
        {"kind": "function", "name": "probe"},
        [{"name": "network", "args": [], "expected": "BLOCKED", "hidden": False}],
    )
    loop = run_tests(
        "def spin():\n    while True:\n        pass\n",
        {"kind": "function", "name": "spin"},
        [{"name": "infinite loop", "args": [], "expected": None, "timeout_ms": 500}],
    )
    return {
        "hardened": net.hardened,
        "network_blocked": net.all_passed,
        "timeout_enforced": bool(loop.tests) and loop.tests[0].status == "timeout",
        "interpreter": _child_python(),
    }
