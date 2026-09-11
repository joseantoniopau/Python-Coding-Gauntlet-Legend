"""Command line entry points."""
from __future__ import annotations

import argparse
import json
import sys

from . import config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="gauntlet",
                                     description=f"{config.APP_NAME} — {config.APP_SUBTITLE}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("play", help="launch the game (default)")
    serve_cmd = sub.add_parser("serve", help="run the server without opening a window")
    serve_cmd.add_argument("--port", type=int, default=None)

    build = sub.add_parser("build-corpus", help="rebuild and validate the question corpus")
    build.add_argument("--report", action="store_true", help="print the validation report")

    sub.add_parser("check", help="verify the execution sandbox")
    sub.add_parser("stats", help="print your current progress")
    doctor = sub.add_parser("doctor", help="diagnose the installation")
    doctor.add_argument("--verbose", action="store_true")

    args = parser.parse_args(argv)
    command = args.command or "play"

    if command == "play":
        from .launcher import main as launch
        return launch()

    if command == "serve":
        from . import server
        from .corpus import ensure
        ensure()
        httpd, url = server.serve(args.port)
        print(f"serving on {url}")
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            httpd.shutdown()
        return 0

    if command == "build-corpus":
        from .corpus import build_all, write
        from .corpus.validate import validate
        problems = build_all()
        report = validate(problems)
        path = write(report.accepted)
        print(f"built {len(problems)} problems, accepted {len(report.accepted)}")
        print(f"errors {len(report.errors)}  warnings {len(report.warnings)}")
        if args.report:
            for issue in report.issues:
                print(f"  [{issue.severity}] {issue.problem_id}: {issue.message}")
        print(f"written to {path}")
        return 0 if report.ok else 1

    if command == "check":
        from . import sandbox
        result = sandbox.self_check()
        print(json.dumps(result, indent=2))
        return 0 if result["network_blocked"] and result["timeout_enforced"] else 1

    if command == "stats":
        from .engine import Game
        game = Game()
        d = game.dashboard()
        p = d["player"]
        print(f"{p['title']} — level {p['level']} ({p['xp']} XP)")
        print(f"readiness {d['readiness']['overall']}%  "
              f"gates {d['readiness']['gates_passed']}/{d['readiness']['gates_total']}")
        print(f"corpus {d['corpus_size']} problems · "
              f"{d['stats'].get('solved', 0)}/{d['stats'].get('total', 0)} cleared")
        for skill in d["skills"][:10]:
            if skill["attempts"]:
                print(f"  {skill['name']:<16} {skill['mastery']:5.1f}  {skill['stage']}")
        return 0

    if command == "doctor":
        from . import sandbox
        from .corpus import corpus_path
        print(f"python       {sys.version.split()[0]}")
        print(f"data dir     {config.data_dir()}")
        print(f"database     {config.db_path()} "
              f"({'present' if config.db_path().exists() else 'not created yet'})")
        print(f"corpus       {config.corpus_path()} "
              f"({'present' if config.corpus_path().exists() else 'not built yet'})")
        print(f"web root     {config.WEB_ROOT} "
              f"({'ok' if (config.WEB_ROOT / 'index.html').exists() else 'MISSING'})")
        check = sandbox.self_check()
        print(f"sandbox      hardened={check['hardened']} "
              f"network_blocked={check['network_blocked']} "
              f"timeout_enforced={check['timeout_enforced']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
