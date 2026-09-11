#!/usr/bin/env python3
"""Start the game from a source checkout, on any platform.

    python3 run.py

This is the no-install path: it only needs Python 3.11+ and a browser. The
packaged macOS .app and the Windows batch file both end up here.
"""
import sys
from pathlib import Path

MINIMUM = (3, 11)

if sys.version_info < MINIMUM:
    sys.exit(
        "Python %d.%d or newer is required; this is %d.%d.\n"
        "Download it from https://www.python.org/downloads/"
        % (MINIMUM + sys.version_info[:2])
    )

sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    # Bare `python3 run.py` plays. Anything else is a subcommand, and must go to
    # the CLI — silently launching the game when asked to rebuild the corpus is
    # worse than an error, because it looks like it worked.
    if len(sys.argv) > 1:
        from gauntlet.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[1:]))
    from gauntlet.launcher import main
    raise SystemExit(main())
