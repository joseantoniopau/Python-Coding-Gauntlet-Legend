"""Refuse to replace a bundle while one of its Python launchers is running."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys


def launcher_pids(processes: str) -> list[int]:
    return [int(match.group(1)) for line in processes.splitlines()
            if (match := re.fullmatch(
                r"\s*(\d+)\s+.+\s+-m\s+gauntlet\.launcher\s*", line))]


def belongs_to_bundle(cwd: Path, bundles: list[Path]) -> bool:
    cwd = cwd.resolve()
    for bundle in bundles:
        bundle = bundle.resolve()
        if cwd == bundle or bundle in cwd.parents:
            return True
        # An earlier installer may already have moved a running app to backup.
        # Its loaded config still points at the original installation path.
        if any(parent.name == bundle.name for parent in cwd.parents):
            return True
    return False


def running_bundles(bundles: list[Path]) -> list[int]:
    processes = subprocess.run(
        ["/bin/ps", "-axo", "pid=,args="], check=True,
        capture_output=True, text=True, timeout=5).stdout
    active = []
    for pid in launcher_pids(processes):
        result = subprocess.run(
            ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True, text=True, timeout=5)
        paths = [Path(line[1:]) for line in result.stdout.splitlines()
                 if line.startswith("n/")]
        if not paths:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue  # It finished between ps and lsof.
            raise RuntimeError(f"Cannot inspect the running game process {pid}.")
        if any(belongs_to_bundle(path, bundles) for path in paths):
            active.append(pid)
    return active


def main(argv: list[str]) -> int:
    try:
        active = running_bundles([Path(path) for path in argv])
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Cannot safely check app state: {exc}", file=sys.stderr)
        return 1
    if active:
        print("Gauntlet Legend is running. Quit its game window, then run the "
              "build again. The installed app was not replaced.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
