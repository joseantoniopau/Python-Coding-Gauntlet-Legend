"""Local HTTP server. Binds to 127.0.0.1 only, with an origin/token guard so a
stray page in another tab cannot drive the game.
"""
from __future__ import annotations

import http.server
import json
import mimetypes
import os
import secrets
import socket
import socketserver
import threading
import traceback
import urllib.parse
from pathlib import Path

from . import config, sandbox, world
from .engine import Game

TOKEN = secrets.token_urlsafe(24)
_LOCK = threading.RLock()
_GAME: Game | None = None


def game() -> Game:
    global _GAME
    with _LOCK:
        if _GAME is None:
            _GAME = Game()
        return _GAME


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "GauntletLegend/1.0"
    protocol_version = "HTTP/1.1"

    # -- plumbing ----------------------------------------------------------
    def log_message(self, fmt, *args):
        if os.environ.get("GAUNTLET_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, ctype: str, *, cache: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control",
                         "public, max-age=3600" if cache else "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload, status: int = 200):
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _guard(self) -> bool:
        """Only this app's own page may call the API."""
        origin = self.headers.get("Origin")
        if origin and not origin.startswith("http://127.0.0.1"):
            self._json({"error": "forbidden origin"}, 403)
            return False
        token = self.headers.get("X-Gauntlet-Token")
        if token != TOKEN:
            self._json({"error": "bad token"}, 403)
            return False
        return True

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}

    # -- routes ------------------------------------------------------------
    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            if not self._guard():
                return
            return self._api_get(path, urllib.parse.parse_qs(parsed.query))
        return self._static(path)

    def do_HEAD(self):  # noqa: N802
        return self.do_GET()

    def do_POST(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        if not self._guard():
            return
        return self._api_post(parsed.path, self._body())

    # -- static ------------------------------------------------------------
    def _static(self, path: str):
        if path in ("/", "/index.html"):
            html = (config.WEB_ROOT / "index.html").read_text()
            # a distinctive placeholder: the obvious name collides with the
            # `window.__GAUNTLET_TOKEN__` identifier on the same line
            html = html.replace("%%GAUNTLET_SESSION_TOKEN%%", TOKEN)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

        clean = os.path.normpath(path).lstrip("/")
        target = (config.WEB_ROOT / clean).resolve()
        try:
            target.relative_to(config.WEB_ROOT.resolve())
        except ValueError:
            return self._send(403, b"forbidden", "text/plain")
        if not target.is_file():
            return self._send(404, b"not found", "text/plain")
        ctype, _ = mimetypes.guess_type(str(target))
        return self._send(200, target.read_bytes(),
                          ctype or "application/octet-stream", cache=True)

    # -- api ---------------------------------------------------------------
    def _api_get(self, path: str, query: dict):
        g = game()
        try:
            if path == "/api/state":
                return self._json(g.dashboard())
            if path == "/api/world":
                return self._json({
                    "regions": world.REGIONS, "bosses": world.BOSSES,
                    "mentors": world.MENTORS, "companions": world.COMPANIONS,
                    "weapons": world.WEAPONS, "armor": world.ARMOR,
                    "achievements": world.ACHIEVEMENTS, "titles": world.TITLES,
                    "boss_phases": world.BOSS_PHASES,
                })
            if path == "/api/shrine":
                return self._json(g.shrine())
            if path == "/api/history":
                pid = (query.get("problem_id") or [None])[0]
                return self._json(g.performance_history(pid))
            if path == "/api/sandbox/check":
                return self._json(sandbox.self_check())
            if path == "/api/export":
                return self._json(g.export())
            if path == "/api/problem":
                pid = (query.get("id") or [""])[0]
                mode = (query.get("mode") or [config.MODE_ADVENTURE])[0]
                return self._json(g.problem(pid, mode=mode))
            if path == "/api/interview/current":
                return self._json(g.interview_current())
            if path == "/api/diagnostic":
                return self._json(g.diagnostic_trials())
            if path == "/api/curriculum":
                from . import curriculum
                return self._json({"objective": curriculum.next_objective(g.skills),
                                   "ladder": curriculum.ladder(g.skills)})
            if path == "/api/story":
                from . import story as storymod
                ctx = g.story_context()
                return self._json({
                    "log": storymod.quest_log(ctx, g.state["story"]),
                    "session": storymod.session_script(g.state["story"]),
                    "honorific": storymod.honorific(g.state["story"]),
                })
            if path == "/api/loadout":
                return self._json(g.loadout())
            if path == "/api/probes":
                return self._json({"charges": g.probes_remaining()})
            if path == "/api/ping":
                return self._json({"ok": True, "version": config.VERSION,
                                   "corpus": len(g.corpus)})
            return self._json({"error": "not found"}, 404)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": str(exc)}, 500)

    def _api_post(self, path: str, body: dict):
        g = game()
        try:
            with _LOCK:
                if path == "/api/encounter/next":
                    return self._json(g.next_encounter(
                        region=body.get("region"),
                        mode=body.get("mode", config.MODE_ADVENTURE),
                        kind=body.get("kind")))
                if path == "/api/encounter/start":
                    return self._json(g.start_encounter(
                        body["problem_id"], mode=body.get("mode",
                                                          config.MODE_ADVENTURE)))
                if path == "/api/run":
                    return self._json(g.run_visible(body.get("code", "")))
                if path == "/api/scratch":
                    return self._json(g.run_code(body.get("code", "")))
                if path == "/api/submit":
                    result = g.submit(body.get("code", ""),
                                      declared_pattern=body.get("declared_pattern", ""),
                                      explanation=body.get("explanation", ""))
                    if g.state.get("interview") and body.get("interview"):
                        result["interview_next"] = g.interview_advance(result)
                    return self._json(result)
                if path == "/api/mcq":
                    return self._json(g.answer_mcq(int(body.get("choice", -1))))
                if path == "/api/hint":
                    return self._json(g.use_hint(int(body.get("level", 1))))
                if path == "/api/shrine/answer":
                    return self._json(g.shrine_answer(body.get("text", "")))
                if path == "/api/boss/start":
                    return self._json(g.start_boss(body.get("boss_id", "")))
                if path == "/api/boss/ladder":
                    return self._json(g.boss_ladder(body.get("boss_id", "")))
                if path == "/api/interview/start":
                    return self._json(g.start_interview(
                        body.get("format", "GAUNTLET"), body.get("profile")))
                if path == "/api/interview/finish":
                    return self._json(g.finish_interview())
                if path == "/api/puzzle":
                    return self._json(g.solve_puzzle(body.get("answer")))
                if path == "/api/diagnostic/check":
                    return self._json(g.diagnostic_check(body.get("trial", ""),
                                                         body.get("answer")))
                if path == "/api/diagnostic/finish":
                    return self._json(g.diagnostic_finish(
                        body.get("answers") or {}, skipped=bool(body.get("skipped"))))
                if path == "/api/story/advance":
                    from . import story as storymod
                    g.state["story"] = storymod.advance_session(g.state["story"]) \
                        or g.state["story"]
                    g.save()
                    return self._json(storymod.session_script(g.state["story"]))
                if path == "/api/probe":
                    return self._json(g.probe(body.get("args", []),
                                              body.get("expected"),
                                              body.get("ops")))
                if path == "/api/equip":
                    return self._json(g.equip(body.get("item_id", "")))
                if path == "/api/unequip":
                    return self._json(g.unequip(body.get("slot", "")))
                if path == "/api/allocate":
                    return self._json(g.allocate(body.get("attribute", ""),
                                                 int(body.get("points", 1))))
                if path == "/api/build":
                    return self._json(g.choose_build(body.get("build", "")))
                if path == "/api/respec":
                    return self._json(g.respec())
                if path == "/api/consumable":
                    return self._json(g.use_consumable(body.get("id", "")))
                if path == "/api/search":
                    return self._json(g.find_secret_location(
                        body.get("region", ""), int(body.get("x", 0)),
                        int(body.get("y", 0))))
                if path == "/api/settings":
                    return self._json(g.set_setting(body["key"], body["value"]))
                if path == "/api/profile":
                    return self._json(g.set_profile(body.get("profile", "")))
                if path == "/api/move":
                    return self._json(g.move(body.get("region", "python_village"),
                                             int(body.get("x", 0)),
                                             int(body.get("y", 0))))
                if path == "/api/import":
                    return self._json(g.import_save(body.get("payload", {})))
                if path == "/api/explain":
                    from .coach import explanation_score
                    enc = g.encounter
                    if not enc:
                        return self._json({"error": "no active encounter"})
                    if enc.mode == config.MODE_INTERVIEW:
                        return self._json({"error": "sealed"})
                    return self._json(explanation_score(body.get("text", ""),
                                                        g.by_id[enc.problem_id]))
            return self._json({"error": "not found"}, 404)
        except KeyError as exc:
            return self._json({"error": f"missing or unknown: {exc}"}, 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": str(exc)}, 500)


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def free_port(preferred: int = 8731) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind(("127.0.0.1", port))
                return probe.getsockname()[1]
        except OSError:
            continue
    return 0


def serve(port: int | None = None, *, open_browser: bool = False) -> tuple:
    port = port or free_port()
    httpd = Server(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?t={TOKEN}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, url
