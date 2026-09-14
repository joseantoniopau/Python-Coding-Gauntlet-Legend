#!/usr/bin/env python3
"""Regenerate the art gallery's fictional cinematic scripts.

Uses only finale.cutscene() and ending.rematch(), both pure composition APIs.
It never instantiates Engine, opens a database, or reads a player's save.
Run with --check to verify the checked-in gallery fixture without writing it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gauntlet import ending, finale, finalexam  # noqa: E402

DESTINATION = ROOT / "web" / "art" / "cinematic-scenes.json"
NOTICE = (
    "ART DEMONSTRATION — all people, rescue counts, assessment results, and "
    "identifiers below are fictional fixtures. This is not a player's save or "
    "evidence of interview readiness."
)


def roster(count: int, *, released: bool = False) -> list[dict]:
    names = ("Ember", "Rowan", "Vale", "Kestrel", "Morrow", "Lark", "Briar")
    faces = ("smith", "ranger", "scholar", "oracle", "druid", "villager", "architect")
    return [
        {
            "id": f"gallery_{'released' if released else 'rescued'}_{i + 1:02d}",
            "name": f"Demo {names[i % len(names)]} {i + 1:02d}",
            "sprite": faces[i % len(faces)],
            "trade": "Fictional gallery cast",
            "region": "python_village",
            "order": i,
            "line": "My name is a fictional gallery example.",
            **({"released_line": "The light went out. I stood up on my own."} if released else {}),
        }
        for i in range(count)
    ]


def report(passed: bool) -> dict:
    return {
        "solved": 5 if passed else 1,
        "total": 6,
        "score": 83 if passed else 17,
        "within_clock": True,
        "clock": "1:52:10",
        "format_label": finalexam.THE_PRACTICAL.label,
        "verdict": {"code": "READY" if passed else "NOT_READY", "headline": "", "body": ""},
        "dominant_signal": "implementation",
        "signal_note": finalexam.BUCKET_MEANING["implementation"],
        "drills": [] if passed else [{
            "cause": "OFF_BY_ONE", "skill": "ARRAY", "occurrences": 2,
            "do": finalexam.DRILL_ACTION["OFF_BY_ONE"],
            "where": "the Village", "region": "python_village",
        }],
    }


def build() -> dict:
    specimens = []
    for identity, label, rescued, released in (
        ("pass_empty", "Demonstration: pass with no rescued cast", 0, 0),
        ("pass_two_rosters", "Demonstration: 6 rescued and 4 independently released", 6, 4),
        ("pass_full", "Demonstration: full 28-person rescued formation", 28, 0),
    ):
        scene = finale.cutscene(
            freed=roster(rescued), released=roster(released, released=True),
            total_captives=28, exam_report=report(True),
            names=["demo_frontier", "demo_window", "demo_counter"],
        )
        problems = finale.validate(scene)
        if problems:
            raise ValueError(f"{identity}: {problems}")
        scene["demonstration"] = True
        specimens.append({"id": identity, "label": label, "scene": scene})

    failure = ending.rematch(exam_report=report(False), still_held=28, carried=0)
    problems = ending.validate_scene(failure)
    if problems:
        raise ValueError(f"rematch: {problems}")
    failure["demonstration"] = True
    specimens.append({
        "id": "rematch", "label": "Demonstration: failed practical and return route",
        "scene": failure,
    })
    return {
        "schema_version": 1,
        "demonstration": True,
        "notice": NOTICE,
        "producers": ["gauntlet.finale.cutscene", "gauntlet.ending.rematch"],
        "regenerate": "python3 scripts/generate_cinematic_fixtures.py",
        "scenes": specimens,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the artifact without writing it")
    args = parser.parse_args()
    content = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not DESTINATION.is_file() or DESTINATION.read_text(encoding="utf-8") != content:
            print(f"Cinematic fixture is missing or stale: {DESTINATION}", file=sys.stderr)
            return 1
        print("Cinematic fixture matches the current pure Python producers.")
        return 0
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text(content, encoding="utf-8")
    print(f"Wrote 4 fictional cinematic specimens: {DESTINATION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
