"""Application launcher.

Starts the local server, opens a chromeless window on it, and shuts everything
down cleanly when that window closes or the app is quit from the Dock.
"""
from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from . import config


def _wait_for_port(port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _chrome_binary() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return shutil.which("chromium") or shutil.which("google-chrome")


def open_window(url: str) -> subprocess.Popen | None:
    """A Chromium app window gives a genuine chromeless app feel. Without one we
    fall back to the default browser, which still works."""
    chrome = _chrome_binary()
    if chrome:
        profile = config.data_dir() / "window"
        profile.mkdir(parents=True, exist_ok=True)
        return subprocess.Popen(
            [chrome, f"--app={url}",
             f"--user-data-dir={profile}",
             "--window-size=1440,940",
             "--no-first-run", "--no-default-browser-check",
             "--disable-background-networking",
             "--disable-sync", "--disable-extensions",
             "--disable-features=Translate,MediaRouter,OptimizationHints"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen(["open", url], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return None


def main() -> int:
    from . import server

    print(f"{config.APP_NAME} {config.VERSION}")
    print(f"save data: {config.data_dir()}")

    # Build and validate the corpus on first run so the first session is instant.
    from .corpus import ensure
    corpus = ensure()
    print(f"corpus: {len(corpus)} validated problems")

    httpd, url = server.serve()
    port = httpd.server_address[1]
    if not _wait_for_port(port):
        print("server failed to start", file=sys.stderr)
        return 1
    print(f"serving on {url}")

    window = None
    if os.environ.get("GAUNTLET_NO_WINDOW") != "1":
        window = open_window(url)

    stopping = {"flag": False}

    def stop(signum=None, frame=None):
        if stopping["flag"]:
            return
        stopping["flag"] = True
        print("\nshutting down…")
        try:
            httpd.shutdown()
        except Exception:
            pass
        if window and window.poll() is None:
            window.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        if window is not None:
            window.wait()          # quit when the app window is closed
            stop()
        else:
            while not stopping["flag"]:
                time.sleep(0.5)
    except KeyboardInterrupt:
        stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
