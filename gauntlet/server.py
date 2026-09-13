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
from dataclasses import asdict
from pathlib import Path

from . import config, sandbox, world
from . import bestiary, classes, dungeons, elements, finalexam, forge
from . import incantation
from . import minirepo
from . import pets, potions, progression
from . import quests, saves, worldgen
# The ten systems that had no door until now. Imported for their ID TABLES and
# their CAPABILITY NAMES only — every rule in them is reached through a Game
# method, because a second copy of a rule in the HTTP layer is how the two
# start disagreeing.
from . import banter, economy, finale, hunters, regalia, sages, sanctuary, upkeep
from .engine import Game

TOKEN = secrets.token_urlsafe(24)
_LOCK = threading.RLock()
# A save export is the biggest honest body, and it is measured in
# hundreds of kilobytes. Past this we are being fed, not asked.
_MAX_BODY = 8 * 1024 * 1024
_GAME: Game | None = None


class _BadRequest(Exception):
    """A malformed request, as opposed to a refused one. 400, not 500."""


def game() -> Game:
    global _GAME
    with _LOCK:
        if _GAME is None:
            _GAME = Game()
        return _GAME


def set_game(instance) -> None:
    """Point the HTTP layer at a particular Game. Tests use this to serve a
    throwaway save; nothing in the shipping app calls it."""
    global _GAME
    with _LOCK:
        _GAME = instance


def _incant_answers(move_id: str, body: dict):
    """The client's IncantationUI sends `holes` positionally plus the assembled
    `line`; incantation.cast wants a hole->text mapping, or the whole line as a
    string. The translation belongs at the door rather than in either of them."""
    answers = body.get("answers")
    if isinstance(answers, dict):
        return {str(k): "" if v is None else str(v) for k, v in answers.items()}
    holes = body.get("holes")
    inc = incantation.BY_ID.get(move_id)
    if isinstance(holes, list) and inc is not None:
        names = [h.name for h in inc.holes]
        return {name: str(value) for name, value in zip(names, holes)
                if value is not None}
    line = body.get("line") or body.get("raw")
    if isinstance(line, str) and line.strip():
        return line.strip()
    return {}


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
        """A body that is not a JSON object is a malformed request, and saying so
        is cheaper for everybody than letting it fall through as {} and surface
        three frames later as a KeyError."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            raise _BadRequest("Content-Length was not a number.")
        if length <= 0:
            return {}
        if length > _MAX_BODY:
            raise _BadRequest(f"that request body is too large "
                              f"({length} bytes; the ceiling is {_MAX_BODY}).")
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise _BadRequest(f"the request body was not valid JSON ({exc}).")
        if not isinstance(parsed, dict):
            raise _BadRequest("the request body must be a JSON object.")
        return parsed

    # -- one reply convention, and the input checks that keep 500s away ----
    def _reply(self, payload, status: int = 200) -> bool:
        """Every new handler answers through here.

        A sealed refusal is 409 — the request was well formed and the game is
        simply in a state where the answer is no. Everything else a module calls
        a refusal rides at 200 with an `error` key, which is the convention the
        existing handlers and the client already speak.
        """
        if isinstance(payload, dict) and payload.get("error") == "sealed":
            status = 409
        self._json(payload, status)
        return True

    def _fail(self, message: str, status: int = 400) -> bool:
        self._json({"error": message}, status)
        return True

    def _need_str(self, body: dict, key: str, *, limit: int = 200):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip():
            self._fail(f"'{key}' must be a non-empty string.")
            return None
        text = value.strip()
        if len(text) > limit:
            self._fail(f"'{key}' is longer than {limit} characters.")
            return None
        return text

    def _opt_str(self, body: dict, key: str, default: str = "", *,
                 limit: int = 200):
        value = body.get(key, default)
        if value is None:
            return default
        if not isinstance(value, str):
            self._fail(f"'{key}' must be a string.")
            return None
        return value.strip()[:limit]

    def _need_int(self, body: dict, key: str, *, low=None, high=None):
        raw = body.get(key)
        if raw is None or isinstance(raw, bool):
            self._fail(f"'{key}' must be a whole number.")
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            self._fail(f"'{key}' must be a whole number.")
            return None
        if (low is not None and value < low) or (high is not None and value > high):
            self._fail(f"'{key}' must be between {low} and {high}.")
            return None
        return value

    def _need_list(self, body: dict, key: str, *, limit: int = 32):
        raw = body.get(key)
        if raw is None:
            return []
        if not isinstance(raw, list):
            self._fail(f"'{key}' must be a list.")
            return None
        if len(raw) > limit:
            self._fail(f"'{key}' may hold at most {limit} entries.")
            return None
        if not all(isinstance(item, str) for item in raw):
            self._fail(f"every entry in '{key}' must be a string.")
            return None
        return raw

    def _need_files(self, body: dict, key: str = "files"):
        """A Mini-Repo working tree: {path: source}, and nothing exotic.

        The engine checks the paths against the repo that handed them out and
        the sandbox refuses a dangerous filename on top of that. This is the
        cheap shape check at the door, so a list of integers becomes a sentence
        rather than a stack trace, and so a tree far larger than any repository
        is turned away before it is copied anywhere.
        """
        raw = body.get(key)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            self._fail(f"'{key}' must be an object of {{path: source}}.")
            return None
        if len(raw) > sandbox.MAX_PROJECT_FILES:
            self._fail(f"a repository holds at most "
                       f"{sandbox.MAX_PROJECT_FILES} files.")
            return None
        total = 0
        for path, value in raw.items():
            if not isinstance(path, str) or not isinstance(value, str):
                self._fail(f"every entry in '{key}' must be text, keyed by "
                           "its path.")
                return None
            if len(path) > 200:
                self._fail("that is not a path in any repository.")
                return None
            total += len(value)
        if total > sandbox.MAX_PROJECT_BYTES:
            self._fail(f"that working tree is {total} bytes; the ceiling is "
                       f"{sandbox.MAX_PROJECT_BYTES}.")
            return None
        return raw

    def _need_dict(self, body: dict, key: str):
        raw = body.get(key)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            self._fail(f"'{key}' must be a JSON object.")
            return None
        return raw

    def _sealed(self, g, capability: str = "BUILD") -> bool:
        """Interview Mode is enforced HERE as well as in the engine.

        finalexam.sealed() is the one question; this asks it at the door. The
        engine refuses too, and so do the modules, but a guarantee that only
        lives three rooms in is a guarantee somebody can walk around.
        """
        enc = g.encounter
        if g.state.get("interview") or (enc is not None
                                        and enc.mode == config.MODE_INTERVIEW):
            self._json(finalexam.refuse(capability), 409)
            return True
        return False

    def _saves_call(self, fn, *args, **kwargs) -> bool:
        """saves.SaveError messages are written to be shown to the player
        verbatim, so they are, at a status that says whose fault it was."""
        try:
            return self._reply(fn(*args, **kwargs))
        except saves.SlotNotFound as exc:
            return self._fail(str(exc), 404)
        except saves.SaveError as exc:
            return self._fail(str(exc), 400)

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
        try:
            body = self._body()
        except _BadRequest as exc:
            return self._json({"error": str(exc)}, 400)
        return self._api_post(parsed.path, body)

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
        ctype = ctype or "application/octet-stream"
        if ctype.startswith(("audio/", "video/")):
            return self._send_range(target, ctype)
        return self._send(200, target.read_bytes(), ctype, cache=True)

    def _send_range(self, target, ctype: str):
        """Serve media with Range support.

        An <audio> element asks for `Range: bytes=0-` and expects a 206 back. A
        plain 200 with the whole file does technically play in Chrome, but it
        buffers the entire track before it starts and cannot seek or loop
        cleanly — which for a seven-megabyte music bed is the difference between
        instant and a stall every time the region changes.
        """
        size = target.stat().st_size
        rng = self.headers.get("Range", "")
        start, end = 0, size - 1
        partial = False

        if rng.startswith("bytes="):
            spec = rng[6:].split(",")[0].strip()
            try:
                first, _, last = spec.partition("-")
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                elif last:                      # a suffix range: last N bytes
                    start = max(0, size - int(last))
                partial = True
            except ValueError:
                partial = False                 # a malformed range is not fatal
            if partial and (start >= size or start > end):
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end = min(end, size - 1)

        length = end - start + 1
        with open(target, "rb") as fh:
            fh.seek(start)
            body = fh.read(length)

        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # -- api ---------------------------------------------------------------
    def _api_get(self, path: str, query: dict):
        g = game()
        try:
            # One Game, one sqlite connection, and a threading server. A read
            # is not read-only down here — every world view folds a fresh
            # snapshot and several of them touch the same cursor, so two
            # overlapping GETs hand each other a half-built row. The client
            # opens the map with five reads at once; without this they race.
            with _LOCK:
                return self._api_get_locked(g, path, query)
        except _BadRequest as exc:
            return self._json({"error": str(exc)}, 400)
        except KeyError as exc:
            return self._json({"error": f"missing or unknown: {exc}"}, 400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": f"the server stumbled on {path}: {exc}",
                               "kind": type(exc).__name__}, 500)

    def _api_get_locked(self, g, path: str, query: dict):
        """Every GET, dispatched with the game already held."""
        if path == "/api/state":
            return self._json(g.dashboard())
        if path == "/api/world":
            return self._json({
                "regions": world.REGIONS, "bosses": world.BOSSES,
                "mentors": world.MENTORS, "companions": world.COMPANIONS,
                "weapons": world.WEAPONS, "armor": world.ARMOR,
                "achievements": world.ACHIEVEMENTS, "titles": world.TITLES,
                "boss_phases": world.BOSS_PHASES,
                # The seeded world. The spec is never serialised into a save
                # — four bytes of seed rebuild it — so the client reads the
                # shape of this run from here.
                "seed": worldgen.seed_text(g.world.seed),
                "regions_order": list(g.world.region_order()),
                "routes": [asdict(r) for r in g.world.routes],
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
        if path == "/api/transfer":
            # The second number, on its own door. Deliberately not folded into
            # /api/state's `readiness`: one of those is a measure of familiarity
            # with taught material and the other is a measure of whether any of
            # it transfers, and a screen that renders them as one number is
            # telling the player something neither of them says.
            return self._json(g.transfer_report())
        if path == "/api/probes":
            return self._json({"charges": g.probes_remaining()})
        # -- Mini-Repo Battles ---------------------------------------------
        if path == "/api/repos":
            return self._json(g.minirepo_board(
                difficulty=(query.get("difficulty") or [""])[0].strip().upper()[:12],
                tag=(query.get("tag") or [""])[0].strip()[:40]))
        if path == "/api/repo":
            # The fight as it stands, including the player's own edits. A
            # reload mid-repo comes back through here.
            return self._reply(g.minirepo_view())
        if path == "/api/ping":
            return self._json({"ok": True, "version": config.VERSION,
                               "corpus": len(g.corpus)})
        if self._world_get(g, path, query):
            return
        return self._json({"error": f"no such endpoint: {path}"}, 404)

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
                    return self._reply(g.use_hint(int(body.get("level", 1))))
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
                    return self._reply(g.probe(body.get("args", []),
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
                    return self._reply(g.use_consumable(body.get("id", "")))
                # The belt. Deliberately its own door rather than a branch of
                # /api/consumable: a consumable is a scroll that changes what
                # the encounter GIVES you, and a potion is a draught that
                # changes what you can survive. They share a verb and nothing
                # else, and folding them together would put the one rule this
                # feature rests on — drinking is not a turn — behind a route
                # whose other half legitimately ends turns.
                #
                # `_reply` maps the sealed refusal to 409, which is what
                # potions.drink returns in a measured run. Nothing here forms a
                # second opinion about the seal; there is exactly one.
                if path == "/api/potion":
                    return self._reply(g.use_potion(body.get("id", "")))
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
                    # This used to test enc.mode itself and answer with a bare
                    # {"error": "sealed"} at 200 — a second path to the same
                    # question, with no capability named and the wrong status.
                    # There is one way to ask whether a capability is open.
                    if finalexam.sealed(enc, "COACH"):
                        return self._reply(finalexam.refuse("COACH"))
                    if enc.repo_id:
                        return self._json({"error": "this is a mini-repo",
                                           "message": "The explanation this "
                                           "encounter wants is a diff."})
                    return self._json(explanation_score(body.get("text", ""),
                                                        g.by_id[enc.problem_id]))
                if self._world_post(g, path, body):
                    return
            return self._json({"error": f"no such endpoint: {path}"}, 404)
        except _BadRequest as exc:
            return self._json({"error": str(exc)}, 400)
        except KeyError as exc:
            return self._json({"error": f"missing or unknown: {exc}"}, 400)
        except (TypeError, ValueError) as exc:
            # A number that was not a number, an id of the wrong shape. The
            # player sent something odd; they have not broken the server. The
            # traceback is still printed, because this is also where a genuine
            # engine bug would land and a 400 must not be where it hides.
            traceback.print_exc()
            return self._json({"error": f"that request did not make sense: {exc}"},
                              400)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"error": f"the server stumbled on {path}: {exc}",
                               "kind": type(exc).__name__}, 500)

    # ======================================================================
    # The world layer.
    #
    # Twenty-one modules were written, self-checked and unreachable from a
    # browser — eleven in an earlier pass, and the ten below it that between
    # them are the town, the shelf, the voices, the regalia, the sanctuaries,
    # the captives, the finale, the hunt, the sages and their arts.
    #
    # Everything here is a thin door onto an engine method that already holds
    # the rules. The server's own two jobs are input validation — nobody gets a
    # stack trace — and the seal: Interview Mode is refused at the door as well
    # as inside, because a guarantee that only lives three rooms in is one
    # somebody can walk around. For several of the doors below that is not
    # belt-and-braces; see the note on _sealed above.
    # ======================================================================
    REGION_IDS = frozenset(r["id"] for r in world.REGIONS)
    # The id tables the new doors check against. Frozen at class-definition
    # time off the modules' own catalogues, so a new potion, a new trial form
    # or a new rung is reachable the moment it is authored and an id that was
    # never authored is a 404 with the name in it rather than a stack trace.
    POTION_IDS = frozenset(potions.BY_ID)
    TRIAL_FORM_IDS = frozenset(form.id for form in economy.TRIAL_FORMS)
    STAGE_KEYS = frozenset(stage.key for sage in sages.SAGES
                           for stage in sage.stages)

    # ------------------------------------------------------------------
    # WHY SO MANY OF THE DOORS BELOW SEAL AT THE DOOR AND NOT ONLY INSIDE.
    #
    # `finalexam.sealed(encounter, capability)` asks about an ENCOUNTER. The
    # engine's town, healer, smith, sanctuary, sage board and finale all ask it
    # that way — and `self.encounter` is None in a measured run whenever the
    # player is between problems, which includes the whole stretch between
    # `start_interview()` and the first `interview_current()`. `sealed(None, X)`
    # is False, so those methods answer normally in that window.
    #
    # `_sealed` here asks the other half of the same question — is a measured
    # run OPEN — which is what `Game._sealed_in_interview` asks internally. It
    # is the one capability check either way: `finalexam.sealed` and
    # `finalexam.refuse`, no second isolation path. This is not a second
    # opinion; it is the same opinion, asked where the encounter is not the
    # only evidence available.
    # ------------------------------------------------------------------

    def _region(self, value: str, *, what: str = "region"):
        """A region id or the empty string. False means a reply has been sent."""
        if value and value not in self.REGION_IDS:
            self._fail(f"no {what} called {value!r}.", 404)
            return False
        return value

    def _need_bool(self, body: dict, key: str, default: bool = False):
        raw = body.get(key, default)
        if not isinstance(raw, bool):
            self._fail(f"'{key}' must be true or false.")
            return None
        return raw

    def _world_get(self, g, path: str, query: dict) -> bool:
        def one(key: str, default: str = "") -> str:
            values = query.get(key) or [default]
            return (values[0] or default).strip()

        # -- classes and the skill tree ------------------------------------
        if path == "/api/classes":
            return self._reply(g.class_selection())
        if path == "/api/class/tree":
            return self._reply(g.class_tree())

        # -- quests --------------------------------------------------------
        if path == "/api/quests":
            region = one("region")
            if region and region not in self.REGION_IDS:
                return self._fail(f"no region called {region!r}.", 404)
            return self._reply(g.quest_board(region))
        if path == "/api/quest":
            quest_id = one("id")
            if quest_id not in quests.QUEST_BY_ID:
                return self._fail(f"no quest called {quest_id!r}.", 404)
            return self._reply(quests.offer(quest_id, g._quest_ctx()))
        if path == "/api/chains":
            return self._reply({"chains": quests.chains_view(g._quest_ctx())})

        # -- companions ----------------------------------------------------
        if path == "/api/pets":
            return self._reply(g.pet_catalogue())
        if path == "/api/pets/discovery":
            pet_id = one("id")
            if pet_id and pet_id not in pets.BY_ID:
                return self._fail(f"no companion called {pet_id!r}.", 404)
            evidence = g._pet_evidence()
            if pet_id:
                return self._reply(pets.discovery_progress(pet_id, evidence))
            return self._reply({
                "progress": [pets.discovery_progress(p, evidence)
                             for p in pets.PET_IDS],
                "found": list(g.state["pets"]["found"]),
                "fallen": list(g.state["pets"].get("fallen") or []),
            })
        if path == "/api/pets/tiers":
            # The ladder, with the roster under each rung, so a player can see
            # the depth they currently have no answer for before they walk into
            # it rather than afterwards.
            return self._reply({"tiers": pets.tier_table(),
                                "limit": pets.ACTIVE_LIMIT,
                                "open_rung": pets.OPEN_RUNG,
                                "free_solution_after": pets.FREE_SOLUTION_AFTER})
        if path == "/api/hint/route":
            # Every road out of the encounter the player is standing in. Pure:
            # it spends nothing, grants nothing, and answers the same for a
            # player with the wrong companion, no companion and a dead one.
            return self._reply(g.hint_route())

        # -- dungeons ------------------------------------------------------
        if path == "/api/dungeons":
            region = one("region")
            if region and region not in self.REGION_IDS:
                return self._fail(f"no region called {region!r}.", 404)
            return self._reply(g.dungeon_list(region))
        if path == "/api/dungeon":
            return self._reply(g.dungeon_state())

        # -- progression ---------------------------------------------------
        if path == "/api/world-map":
            return self._reply(g.world_map())
        if path == "/api/region":
            region_id = one("id") or g.state["player"].get("region", "")
            if region_id not in self.REGION_IDS:
                return self._fail(f"no region called {region_id!r}.", 404)
            return self._reply(g.region_view(region_id))
        if path == "/api/routes":
            region = one("region")
            if region and region not in self.REGION_IDS:
                return self._fail(f"no region called {region!r}.", 404)
            prog = progression.snapshot(g.state, g.skills,
                                        readiness=g._readiness())
            here = region or prog["region"]
            return self._reply({
                "here": here,
                # Every road, hidden ones excepted until they are found: a
                # wall the player can read is a goal; one they cannot see is a
                # dead end, and the rule says learning never dead-ends.
                "routes": [progression.route_status(r, prog, frm=here)
                           for r in progression.routes_from(here)
                           if r.need.kind != "discovery"
                           or r.id in (g.state["world"].get("discovered") or [])],
                "open": [s["id"] for s in progression.open_routes(prog, here)],
                "reachable": sorted(progression.reachable(prog, here)),
            })
        if path == "/api/events":
            prog = progression.snapshot(g.state, g.skills,
                                        readiness=g._readiness())
            return self._reply(progression.events_view(prog))
        if path == "/api/todo":
            # The no-dead-end guarantee, as an endpoint. It is never empty.
            return self._reply({"todo": g.things_to_do()})

        # -- saves ---------------------------------------------------------
        if path == "/api/saves":
            return self._saves_call(g.save_slots)

        # -- legendaries ---------------------------------------------------
        if path == "/api/legendaries":
            return self._reply(g.legendary_catalogue())
        if path == "/api/legendary":
            artifact_id = one("id")
            if not artifact_id:
                return self._fail("'id' is required.")
            entry = g.legendary(artifact_id)
            return self._reply(entry, 404 if entry.get("error") else 200)
        if path == "/api/hand":
            return self._reply(g.hand_offer())

        # -- the forge -----------------------------------------------------
        # Read-only and NOT sealed. Looking at the bench during a measured run
        # tells the player nothing about the problem in front of them, and a
        # screen that refuses to show you what you own is a refusal with no
        # rule behind it. What is sealed is the blade's NUMBERS, which
        # forge.active() removes inside the engine, and the upgrade itself.
        if path == "/api/forge":
            blade_id = one("blade")
            if blade_id and blade_id not in forge.BLADE_BY_ID:
                return self._fail(f"no blade called {blade_id!r}.", 404)
            return self._reply(g.smith(blade_id))
        if path == "/api/forge/technique":
            blade_id = one("blade")
            if blade_id and blade_id not in forge.BLADE_BY_ID:
                return self._fail(f"no blade called {blade_id!r}.", 404)
            return self._reply(g.forge_technique(blade_id))
        if path == "/api/forge/swap":
            blade_id = one("blade")
            if blade_id and blade_id not in forge.BLADE_BY_ID:
                return self._fail(f"no blade called {blade_id!r}.", 404)
            return self._reply(g.forge_swap(blade_id))
        if path == "/api/forge/metals":
            # Where every metal drops, how hard it hits there and roughly how
            # many fights a bar is. This is the panel that stops a player
            # giving up, so it is one call and it is always available.
            return self._reply({
                "metals": [{**m.to_dict(), **forge.counsel(m.id)}
                           for m in forge.METALS],
                "bag": (g.forge_card() or {}).get("bag", []),
            })

        # -- the wheel -----------------------------------------------------
        # Six elements, six statuses, six hazards, eight boots, seventeen
        # regions and the twelve potions, straight off elements.py's and
        # potions.py's own tables.
        #
        # ONE CALL, CACHED BY THE CLIENT, AND NOT SEALED. None of it is a
        # reading of any particular fight: it is the rulebook, and a rulebook
        # the player cannot read is a mechanic they conclude is broken. What IS
        # sealed is which element the thing in front of them is made of, and
        # that lives on the encounter payload behind WEAKNESS_MAP where it
        # belongs.
        #
        # It exists so no table in this file has a second copy in JavaScript.
        # A status's name, its duration and what cures it are elements.py's to
        # say; the client draws what it is told and owns none of it.
        if path == "/api/wheel":
            return self._reply({
                "elements": [elements.element_view(eid)
                             for eid in elements.ELEMENT_IDS],
                "neutral": elements.element_view(elements.NEUTRAL),
                "opposed": dict(elements.OPPOSED),
                "secondary": dict(elements.SECONDARY),
                "matchups": {kind: {"multiplier": mult,
                                    "label": elements.MATCHUP_LABEL[kind]}
                             for kind, mult in elements.MATCHUP_MULT.items()},
                "statuses": [asdict(st) for st in elements.STATUSES.values()],
                # What a monster can spend its focus on, one per element plus
                # the neutral one. Shipped so the focus bar can be drawn with
                # the line it is filling toward: a gauge creeping up to nothing
                # in particular teaches a player nothing, and a gauge creeping
                # up to SUNDER · 12 teaches them to watch it.
                "specials": [asdict(sp) for sp in bestiary.SPECIALS],
                "cures": {k: list(v) for k, v in elements.CURES.items()},
                "hazards": [asdict(h) for h in elements.HAZARDS.values()],
                "boots": [asdict(b) for b in elements.BOOTS],
                "affinities": elements.region_affinities(),
                "potions": [p.to_dict() for p in potions.CATALOGUE],
                # The two sentences that are the whole feature, said by the
                # modules that enforce them rather than retyped in the client.
                "potion_rule": "A draught is free. A second draught costs a cast.",
                "turn_rule": "One graded submission is one turn, right or wrong.",
                "limits": {
                    "worst_case_multiplier": elements.WORST_CASE_MULTIPLIER,
                    "max_fight_stretch": elements.MAX_FIGHT_STRETCH,
                    "resist_cap": elements.RESIST_CAP,
                    "armour_point_cap": elements.ARMOUR_POINT_CAP,
                },
            })

        # -- the keys and the door they open -------------------------------
        #
        # OPEN, and checked against all three questions in
        # docs/10-sealed-views.md §1. The SWAP test: a key is a boss you beat,
        # and it does not move when the question on the screen does. The
        # IN-FORCE test: a key is derived from `cleared_bosses` and no seal
        # suspends it. The SPEND test: it names bosses, roads and a door frame
        # in a village square, and has never seen a problem.
        #
        # THE PORTAL PANEL IS ALSO WHERE A PLAYER WOULD MOST EASILY CONCLUDE
        # THE EXAM IS BEHIND IT, which is why both payloads carry
        # `practical`, from `Game.practical_access()`: the measurement is
        # reachable from the menu with zero keys, and the screen that counts
        # the keys is the screen that has to say so.
        if path == "/api/keys":
            return self._reply(g.keyring())
        if path == "/api/portal":
            return self._reply(g.portal())

        # -- the one who is watching ---------------------------------------
        # A read plus a small write — the rotation advances, so he does not
        # open with the same sentence twice — which is the same bargain the
        # town's voices already make, and it is why the engine saves after it.
        #
        # The seal is asked INSIDE, in `Game.antagonist_view`, and asked of the
        # RUN rather than of an encounter: `antagonist.speak` consults
        # `finalexam.sealed(encounter, capability)`, which is the right question
        # but is unanswerable between two questions of a measured run, where
        # there is no encounter. A measured run gets his standing and no lines.
        if path == "/api/antagonist":
            return self._reply(g.antagonist_view())

        # -- the spell he casts before the practical -----------------------
        # Read-only narration. It is NOT sealed: the spell is the reason the
        # exam takes what it takes, and a player who cannot see the reason is
        # simply told less about a rule that binds them either way. See
        # docs/10-sealed-views.md — this is world, not problem.
        if path == "/api/unmaking":
            return self._reply(g.unmaking_view())

        # -- the final exam ------------------------------------------------
        if path == "/api/exam/ladder":
            return self._reply(g.exam_ladder())

        # -- worldgen ------------------------------------------------------
        if path == "/api/world/card":
            return self._reply(g.world_card())

        # -- incantation combat --------------------------------------------
        if path == "/api/incantation":
            region = one("region")
            if region and region not in self.REGION_IDS:
                return self._fail(f"no region called {region!r}.", 404)
            return self._reply(g.incantation_encounters(region))
        if path == "/api/incantation/state":
            return self._reply(g.incantation_view())

        # -- the town ------------------------------------------------------
        # Reading the square is never sealed. Health is free, the Mender says
        # so before she is asked, and a screen that refuses to show a player
        # what their own armour looks like is a refusal with no rule behind it.
        # What IS sealed is the healing, the mending and the purchase, below.
        if path == "/api/town":
            return self._reply(g.town())
        if path == "/api/town/quote":
            piece = one("piece")
            if piece and piece not in upkeep.PIECES:
                return self._fail(f"nobody wears a {piece!r}.", 404)
            return self._reply(g.repair_quote(piece))

        # -- the shelf and the board ---------------------------------------
        # Prices are not a hint. Seventeen vendors and the broker's board are
        # read freely; spending is a POST and is sealed there.
        if path == "/api/shop":
            region = self._region(one("region"))
            if region is False:
                return True
            return self._reply(g.shop(region))
        if path == "/api/broker":
            region = self._region(one("region"))
            if region is False:
                return True
            return self._reply(g.broker(region))

        # -- the hidden healers --------------------------------------------
        # A log of people who were found by being hurt in the right place.
        # Nothing here is about the problem in front of the player.
        if path == "/api/sanctuaries":
            return self._reply(g.sanctuary_view())

        # -- the people the bosses took ------------------------------------
        # Large and static-ish: seventeen villages' worth of faces and trades.
        # Fetch it when the roll call opens, not on every frame.
        if path == "/api/rollcall":
            return self._reply(g.roll_call())

        # -- the secret arts this playthrough knows ------------------------
        # What you own, like the forge. The arts a player has NOT been taught
        # are named on the sage board and their lines are not rendered until
        # they are earned, so this leaks nothing.
        if path == "/api/arts":
            return self._reply(g.art_book())

        # -- regalia -------------------------------------------------------
        # SEALED, and this one is not belt-and-braces. `regalia.view` takes
        # `mode=` and `sealed=` and zeroes the schedule when either says so;
        # `Game.regalia_view()` passes neither, so inside a measured run this
        # screen would report a threshold scale and an intervention count that
        # are NOT in force. Reporting numbers that are not in force is the
        # SKILL_STATE leak wearing a different hat. The capability is PET,
        # which is what regalia.py's own WIRING names.
        if path == "/api/regalia":
            if self._sealed(g, "PET"):
                return True
            return self._reply(g.regalia_view())

        # -- the sages -----------------------------------------------------
        # SEALED. `sages.available_in` already refuses a sealed run — the
        # module decided a sage does not speak during a measurement — but it
        # decides it from the encounter, and between problems there is not one.
        # Refused here with the capability named, which is what a screen needs
        # to say WHICH thing was taken rather than "409".
        if path == "/api/sage":
            if self._sealed(g, sages.CAPABILITY):
                return True
            region = self._region(one("region"))
            if region is False:
                return True
            return self._reply(g.sage_board(region))

        # -- the hunt ------------------------------------------------------
        # DEGRADE — docs/10-sealed-views.md §4.F. This used to refuse outright,
        # and the reason was sound at the time: `hunt_view` computed readiness
        # with `sealed` at its default and would have reported a preparation
        # score counting bonuses that are not in play.
        #
        # It is no longer the whole screen. Since the chapter ramp landed,
        # everything except readiness is player-independent — `hunters.pace_for`
        # returns the cast band, the strike multiplier and the teaching stance
        # from the chapter and the region id alone — and
        # `readiness_from_game` takes `build_sealed=`. The engine now passes the
        # seal down and serves the view with the readiness readout at zero and a
        # line saying why, which is strictly better than a 409: a refusal
        # teaches the player nothing and a zeroed number teaches them exactly
        # what the seal took.
        #
        # The payload carries `client`, which is hunters.client_payload() —
        # static for the life of the process and the bulk of the response.
        # Cache it; see api.js.
        if path == "/api/hunt":
            region = self._region(one("region"))
            if region is False:
                return True
            return self._reply(g.hunt_view(region))
        return False

    def _world_post(self, g, path: str, body: dict) -> bool:
        # -- classes -------------------------------------------------------
        # A skill tree is BUILD. Interview Mode measures what the player can do
        # without one, so it is sealed for the length of the run.
        if path == "/api/class/choose":
            if self._sealed(g):
                return True
            class_id = self._need_str(body, "class_id", limit=40)
            if class_id is None:
                return True
            if class_id not in classes.CLASS_BY_ID:
                return self._fail(f"no class called {class_id!r}.", 404)
            return self._reply(g.choose_class(class_id))
        if path == "/api/class/spend":
            if self._sealed(g):
                return True
            node_id = self._need_str(body, "node_id", limit=60)
            if node_id is None:
                return True
            if node_id not in classes.NODE_BY_ID:
                return self._fail(f"no skill node called {node_id!r}.", 404)
            return self._reply(g.spend_node(node_id))
        if path == "/api/class/respec":
            if self._sealed(g):
                return True
            scope = self._opt_str(body, "scope", "all", limit=20)
            if scope is None:
                return True
            if scope not in ("all", "branch"):
                return self._fail("'scope' must be 'all' or 'branch'.")
            branch = self._opt_str(body, "branch_id", "", limit=60)
            if branch is None:
                return True
            if scope == "branch" and not branch:
                return self._fail("a branch respec needs a 'branch_id'.")
            return self._reply(g.class_respec(scope=scope, branch_id=branch))
        if path == "/api/class/dual":
            if self._sealed(g):
                return True
            class_id = self._need_str(body, "class_id", limit=40)
            if class_id is None:
                return True
            if class_id not in classes.CLASS_BY_ID:
                return self._fail(f"no class called {class_id!r}.", 404)
            return self._reply(g.choose_dual(class_id))

        # -- quests --------------------------------------------------------
        if path in ("/api/quest/accept", "/api/quest/abandon", "/api/quest/turnin"):
            if self._sealed(g):
                return True
            quest_id = self._need_str(body, "quest_id", limit=60)
            if quest_id is None:
                return True
            if quest_id not in quests.QUEST_BY_ID:
                return self._fail(f"no quest called {quest_id!r}.", 404)
            if path == "/api/quest/accept":
                return self._reply(g.accept_quest(quest_id))
            if path == "/api/quest/abandon":
                return self._reply(g.abandon_quest(quest_id))
            return self._reply(g.turn_in_quest(quest_id))

        # -- companions ----------------------------------------------------
        if path == "/api/pets/active":
            if self._sealed(g, "PET"):
                return True
            pet_ids = self._need_list(body, "pet_ids", limit=pets.ACTIVE_LIMIT * 4)
            if pet_ids is None:
                return True
            unknown = [p for p in pet_ids if p not in pets.BY_ID]
            if unknown:
                return self._fail(f"no companion called {unknown[0]!r}.", 404)
            return self._reply(g.set_active_pets(pet_ids))
        if path == "/api/pet/intervene":
            # A companion costs a hint and caps the rank; the engine charges it.
            # In a measured run no companion speaks at all.
            if self._sealed(g, "PET"):
                return True
            signals = self._need_dict(body, "signals")
            if signals is None:
                return True
            event = g.pet_intervention(signals)
            return self._reply({"pet": event})
        if path == "/api/pet/dismiss":
            if self._sealed(g, "PET"):
                return True
            return self._reply(g.dismiss_pet())
        if path == "/api/pet/recall":
            if self._sealed(g, "PET"):
                return True
            pet_id = (body or {}).get("pet_id")
            if pet_id not in pets.BY_ID:
                return self._fail(f"no companion called {pet_id!r}.", 404)
            return self._reply(g.recall_pet(pet_id))
        if path == "/api/pet/fall/ack":
            # The client has played the barrow scene. The FACT stays in the save
            # forever — the legendary return is gated on it — and only the
            # undelivered scene is cleared.
            return self._reply(g.acknowledge_fall())

        # -- dungeons ------------------------------------------------------
        if path == "/api/dungeon/enter":
            if self._sealed(g):
                return True
            dungeon_id = self._need_str(body, "dungeon_id", limit=60)
            if dungeon_id is None:
                return True
            if dungeon_id not in dungeons.DUNGEON_BY_ID:
                return self._fail(f"no dungeon called {dungeon_id!r}.", 404)
            return self._reply(g.enter_dungeon(dungeon_id))
        if path == "/api/dungeon/move":
            if self._sealed(g):
                return True
            room = self._need_int(body, "room", low=0, high=4096)
            return True if room is None else self._reply(g.dungeon_move(room))
        if path == "/api/dungeon/engage":
            if self._sealed(g):
                return True
            return self._reply(g.dungeon_engage())
        if path == "/api/dungeon/retreat":
            if self._sealed(g):
                return True
            return self._reply(g.dungeon_retreat())
        if path == "/api/dungeon/leave":
            if self._sealed(g):
                return True
            return self._reply(g.leave_dungeon())

        # -- progression ---------------------------------------------------
        if path == "/api/travel":
            if self._sealed(g):
                return True
            route_id = self._need_str(body, "route", limit=80)
            if route_id is None:
                return True
            if route_id not in progression.ROUTE_BY_ID:
                return self._fail(f"no road called {route_id!r}.", 404)
            return self._reply(g.travel(route_id))
        if path == "/api/route/discover":
            if self._sealed(g):
                return True
            route_id = self._need_str(body, "route", limit=80)
            if route_id is None:
                return True
            result = progression.discover_route(g.state, route_id)
            if result.get("ok"):
                g.save()
            return self._reply(result)

        # -- saves ---------------------------------------------------------
        # Saving during a measured run is allowed; it banks the run, it does not
        # help with it. LOADING is sealed, because a load mid-exam is a retry.
        if path == "/api/save":
            ordinal = self._need_int(body, "ordinal", low=1,
                                     high=saves.MANUAL_SLOTS)
            if ordinal is None:
                return True
            name = self._opt_str(body, "name", "", limit=60)
            note = self._opt_str(body, "note", "", limit=200)
            if name is None or note is None:
                return True
            return self._saves_call(g.save_to_slot, ordinal, name, note)
        if path == "/api/load":
            if self._sealed(g):
                return True
            slot = body.get("slot_id", body.get("slot"))
            if not isinstance(slot, (str, int)) or isinstance(slot, bool):
                return self._fail("'slot_id' must be a slot id, like 3 or "
                                  "'slot:3'.")
            return self._saves_call(g.load_slot, slot)
        if path == "/api/undo":
            if self._sealed(g):
                return True
            return self._saves_call(g.undo_load)
        if path == "/api/slot/rename":
            slot = body.get("slot_id", body.get("slot"))
            if not isinstance(slot, (str, int)) or isinstance(slot, bool):
                return self._fail("'slot_id' must be a slot id, like 3 or "
                                  "'slot:3'.")
            name = self._opt_str(body, "name", "", limit=60)
            if name is None:
                return True
            return self._saves_call(saves.rename_slot, g.conn, slot, name)
        if path == "/api/slot/delete":
            slot = body.get("slot_id", body.get("slot"))
            if not isinstance(slot, (str, int)) or isinstance(slot, bool):
                return self._fail("'slot_id' must be a slot id, like 3 or "
                                  "'slot:3'.")
            return self._saves_call(saves.delete_slot, g.conn, slot)
        if path == "/api/slot/export":
            slot = body.get("slot_id", body.get("slot"))
            if not isinstance(slot, (str, int)) or isinstance(slot, bool):
                return self._fail("'slot_id' must be a slot id, like 3 or "
                                  "'slot:3'.")
            # No path: the envelope goes back over the wire and the browser
            # writes the file. The server never touches the player's disk.
            return self._saves_call(saves.export_slot, g.conn, slot)
        if path == "/api/slot/import":
            if self._sealed(g):
                return True
            envelope = self._need_dict(body, "payload")
            if envelope is None:
                return True
            if not envelope:
                return self._fail("'payload' must be an exported save envelope.")
            ordinal = body.get("ordinal")
            if ordinal is not None and (isinstance(ordinal, bool)
                                        or not isinstance(ordinal, (int, str))):
                return self._fail("'ordinal' must be a slot number.")
            name = self._opt_str(body, "name", "", limit=60)
            if name is None:
                return True
            return self._saves_call(saves.import_slot, g.conn, envelope,
                                    ordinal=ordinal, name=name)

        # -- legendaries ---------------------------------------------------
        if path == "/api/hand/use":
            # The Hand is sealed in every measured mode by its own rule, and the
            # engine refuses too. This is the third lock on the same door.
            if self._sealed(g, "OBLIGING_HAND"):
                return True
            return self._reply(g.use_hand())

        # -- the forge -----------------------------------------------------
        # An upgrade is BUILD, and BUILD is what the Editor Automaton takes and
        # what the practical takes entirely. Sealed at the door as well as in
        # the engine, because a guarantee that only lives three rooms in is one
        # somebody can walk around.
        if path in ("/api/forge/upgrade", "/api/forge/rack",
                    "/api/forge/unrack"):
            if self._sealed(g, forge.FORGE_CAPABILITY):
                return True
            blade_id = self._opt_str(body, "blade", "", limit=60)
            if blade_id is None:
                return True
            if blade_id and blade_id not in forge.BLADE_BY_ID:
                return self._fail(f"no blade called {blade_id!r}.", 404)
            if path == "/api/forge/upgrade":
                return self._reply(g.forge_upgrade(blade_id))
            if path == "/api/forge/rack":
                return self._reply(g.forge_rack(blade_id))
            return self._reply(g.forge_unrack())

        # -- the final exam ------------------------------------------------
        # NOT sealed: this is how a player enters the thing that seals them.
        if path == "/api/exam/start":
            profile = self._opt_str(body, "profile", "", limit=40)
            if profile is None:
                return True
            if profile and profile not in config.INTERVIEW_PROFILES:
                return self._fail(f"no profile called {profile!r}.", 404)
            return self._reply(g.start_interview("FINAL_EXAM", profile or None))
        if path == "/api/exam/finish":
            seconds = self._need_dict(body, "seconds_by_segment")
            if seconds is None:
                return True
            bad = [k for k, v in seconds.items()
                   if isinstance(v, bool) or not isinstance(v, (int, float))]
            if bad:
                return self._fail(f"'seconds_by_segment[{bad[0]!r}]' must be "
                                  "a number of seconds.")
            return self._reply(g.finish_exam(seconds or None))

        # -- worldgen ------------------------------------------------------
        if path == "/api/world/new":
            if self._sealed(g):
                return True
            seed = body.get("seed", 0)
            if isinstance(seed, bool) or not isinstance(seed, (int, str)):
                return self._fail("'seed' must be a number or a world code "
                                  "like 'K7P4-2QX'.")
            try:
                if seed:
                    worldgen.parse_seed(seed)
            except (ValueError, TypeError) as exc:
                return self._fail(f"that is not a world code: {exc}")
            return self._reply(g.new_world(seed))

        # -- Mini-Repo Battles ---------------------------------------------
        #
        # Three doors. `start` is an overworld action and is sealed during a
        # measured run like every other one; `run` and `submit` are the fight
        # itself, and sealing those would make a Mini-Repo unplayable in the
        # one mode it most belongs in. What Interview Mode takes off a
        # Mini-Repo is decided by finalexam.sealed() inside the engine, and
        # nowhere else.
        if path == "/api/repo/start":
            repo_id = self._opt_str(body, "repo_id", limit=60)
            if repo_id is None:
                return True
            if repo_id and repo_id not in minirepo.REPOS:
                return self._fail(f"no mini-repo called {repo_id!r}.", 404)
            enc = g.encounter
            if enc is not None and enc.repo_id:
                # Answered before the generic seal, which would otherwise say
                # "class bonuses do not work here" at a player whose actual
                # problem is that they already have a repository open — and
                # whose edits are sitting on that encounter. The engine either
                # hands that fight back or refuses to throw it away.
                return self._reply(g.start_minirepo(repo_id))
            if self._sealed(g):
                return True
            mode = self._opt_str(body, "mode", config.MODE_ADVENTURE, limit=20)
            if mode is None:
                return True
            if mode not in (config.MODE_ADVENTURE, config.MODE_INTERVIEW):
                return self._fail(f"{mode!r} is not a mode.")
            difficulty = self._opt_str(body, "difficulty", limit=12)
            if difficulty is None:
                return True
            return self._reply(g.start_minirepo(
                repo_id, mode=mode, difficulty=difficulty.upper()))
        if path == "/api/repo/run":
            files = self._need_files(body)
            if files is None:
                return True
            return self._reply(g.minirepo_run(files))
        if path == "/api/repo/submit":
            files = self._need_files(body)
            if files is None:
                return True
            # `full_tree` says whether what arrived is the player's WHOLE
            # working tree. The editor sends everything, so it is; a partial
            # save must say so, or every test file it did not send reads as a
            # deletion and an honest player is accused of cheating.
            full_tree = body.get("full_tree", True)
            if not isinstance(full_tree, bool):
                return self._fail("'full_tree' must be true or false.")
            return self._reply(g.minirepo_submit(files, full_tree=full_tree))
        if path == "/api/repo/leave":
            return self._reply(g.leave_minirepo())

        # -- incantation combat --------------------------------------------
        if path == "/api/incant/start":
            if self._sealed(g):
                return True
            encounter_id = self._need_str(body, "encounter_id", limit=60)
            if encounter_id is None:
                return True
            # bestiary.battle_context does not raise on an unknown id — it hands
            # back an empty battlefield, which starts a fight with nothing in it.
            # The engine's try/except therefore never fires. Refused here.
            if encounter_id not in bestiary.ENCOUNTER_BY_ID:
                return self._fail(f"no incantation encounter called "
                                  f"{encounter_id!r}.", 404)
            return self._reply(g.start_incantation(encounter_id))
        if path == "/api/incant/cast":
            if self._sealed(g):
                return True
            move_id = self._need_str(body, "move_id", limit=60)
            if move_id is None:
                return True
            if move_id not in incantation.BY_ID:
                return self._fail(f"no incantation called {move_id!r}.", 404)
            return self._reply(g.incantation_cast(move_id,
                                                  _incant_answers(move_id, body)))
        if path == "/api/incant/leave":
            if self._sealed(g):
                return True
            return self._reply(g.leave_incantation())

        # -- the healer and the smith --------------------------------------
        # Both sealed as BUILD, which is what upkeep.UPKEEP_CAPABILITY is and
        # what the engine returns when it catches this itself. Healing is free
        # and the refusal is not about the money: whatever you break in an exam,
        # you break in the exam only.
        if path == "/api/town/heal":
            if self._sealed(g, upkeep.UPKEEP_CAPABILITY):
                return True
            return self._reply(g.heal())
        if path == "/api/town/repair":
            if self._sealed(g, upkeep.UPKEEP_CAPABILITY):
                return True
            piece = self._opt_str(body, "piece", "", limit=40)
            if piece is None:
                return True
            # "" is every piece, cheapest-first until the gold runs out, which
            # is the normal case for a poor player and deliberately not an
            # error. A piece nobody wears is.
            if piece and piece not in upkeep.PIECES:
                return self._fail(f"nobody wears a {piece!r}.", 404)
            return self._reply(g.repair(piece))

        # -- the shelf -----------------------------------------------------
        # A purchase during a measured run is a consumable acquired mid-exam.
        # The engine refuses it through `_sealed_in_interview` and names BUILD;
        # the door says the same thing at the same capability.
        if path == "/api/shop/buy":
            if self._sealed(g):
                return True
            potion_id = self._need_str(body, "potion_id", limit=60)
            if potion_id is None:
                return True
            if potion_id not in self.POTION_IDS:
                return self._fail(f"no potion called {potion_id!r}.", 404)
            region = self._opt_str(body, "region", "", limit=60)
            if region is None:
                return True
            if self._region(region) is False:
                return True
            quantity = 1
            if body.get("quantity") is not None:
                # A hundred doses is not a shopping trip, it is a typo or a
                # fuzzer. Either way the answer is a sentence.
                quantity = self._need_int(body, "quantity", low=1, high=99)
                if quantity is None:
                    return True
            return self._reply(g.buy_potion(potion_id, region_id=region,
                                            quantity=quantity))

        # -- the challenge broker ------------------------------------------
        # `open` is sealed by the engine. `close` is NOT — and it pays gold,
        # records income and settles a contract, which is the world advancing
        # under a player who is supposed to be sealed off from it. Refused here
        # at the same capability the opening refusal names. Nothing is lost by
        # it: a trial that could not be opened during the run cannot need
        # settling during the run either.
        if path == "/api/broker/open":
            if self._sealed(g):
                return True
            form_id = self._need_str(body, "form_id", limit=60)
            if form_id is None:
                return True
            if form_id not in self.TRIAL_FORM_IDS:
                return self._fail(f"no trial called {form_id!r}.", 404)
            region = self._opt_str(body, "region", "", limit=60)
            if region is None or self._region(region) is False:
                return True
            return self._reply(g.open_trial(form_id, region_id=region))
        if path == "/api/broker/close":
            if self._sealed(g):
                return True
            abandon = self._need_bool(body, "abandon", False)
            if abandon is None:
                return True
            return self._reply(g.close_trial(abandon=abandon))

        # -- the hidden healers --------------------------------------------
        # Sitting down is free, for the same reason the Mender is free, and
        # sealed for the same reason the Mender is sealed.
        if path == "/api/sanctuary/rest":
            if self._sealed(g, sanctuary.SANCTUARY_CAPABILITY):
                return True
            sanctuary_id = self._need_str(body, "sanctuary_id", limit=60)
            if sanctuary_id is None:
                return True
            if sanctuary_id not in sanctuary.BY_ID:
                return self._fail(f"no sanctuary called {sanctuary_id!r}.", 404)
            return self._reply(g.sanctuary_rest(sanctuary_id))

        # -- the spell has been shown once ---------------------------------
        # A latch, not a grant: it only decides whether the NEXT cast is the
        # full telling or the wordless short form. It hands out nothing, so it
        # is not sealed.
        if path == "/api/unmaking/seen":
            return self._reply(g.mark_unmaking_seen())

        # -- the town's forty-seven voices ---------------------------------
        # POST rather than GET because both of these WRITE: the rotation
        # advances so the same person does not open with the same sentence
        # twice, and the save is written afterwards.
        #
        # Sealed at WEAKNESS_MAP, which is what banter.BEAT_CAPABILITY maps its
        # AREA and GEAR beats to and what `banter.refusal()` already names — a
        # townsperson reading the local element and your boots at you during a
        # measured run is the tactical read arriving through a friendlier face.
        if path == "/api/town/talk":
            if self._sealed(g, banter.BEAT_CAPABILITY[banter.AREA]):
                return True
            region = self._opt_str(body, "region", "", limit=60)
            if region is None or self._region(region) is False:
                return True
            return self._reply(g.town_talk(region))
        if path == "/api/npc/speak":
            if self._sealed(g, banter.BEAT_CAPABILITY[banter.AREA]):
                return True
            npc_id = self._need_str(body, "npc_id", limit=60)
            if npc_id is None:
                return True
            if npc_id not in banter.SPEAKERS:
                return self._fail(f"nobody here is called {npc_id!r}.", 404)
            return self._reply(g.speak_to(npc_id))

        # -- regalia -------------------------------------------------------
        # Putting an object on a companion changes how OFTEN it may speak and
        # how EARLY. That is loadout, so it is sealed, and at PET because that
        # is the crutch the object is attached to. Passing "" takes the worn
        # object off and is the one gesture that is always allowed outside a
        # run — a player must never be stuck wearing something.
        if path == "/api/regalia/wear":
            if self._sealed(g, "PET"):
                return True
            regalia_id = self._opt_str(body, "regalia_id", "", limit=60)
            if regalia_id is None:
                return True
            if regalia_id and regalia_id not in regalia.BY_ID:
                return self._fail(f"no regalia called {regalia_id!r}.", 404)
            return self._reply(g.wear_regalia(regalia_id))

        # -- the sixteen hidden sages --------------------------------------
        # All three sealed at sages.CAPABILITY ("MENTOR"). `begin_gauntlet`
        # refuses on its own when an encounter is open; `gauntlet_encounter`
        # and `gauntlet_stage` never do — the first would open an ordinary
        # adventure encounter in the middle of a measured run and the second
        # would hand over a secret art. Both are refused here.
        if path in ("/api/sage/begin", "/api/sage/encounter", "/api/sage/stage"):
            if self._sealed(g, sages.CAPABILITY):
                return True
            if path == "/api/sage/begin":
                region = self._opt_str(body, "region", "", limit=60)
                if region is None or self._region(region) is False:
                    return True
                return self._reply(g.begin_gauntlet(region))
            stage_key = self._need_str(body, "stage_key", limit=40)
            if stage_key is None:
                return True
            if stage_key not in self.STAGE_KEYS:
                return self._fail(f"no rung called {stage_key!r}.", 404)
            if path == "/api/sage/encounter":
                return self._reply(g.gauntlet_encounter(stage_key))
            # Note what is NOT in this body: whether the rung was passed. The
            # engine reads that off the attempts table. A client cannot assert
            # its way to a secret art.
            return self._reply(g.gauntlet_stage(stage_key))

        # -- the last scene ------------------------------------------------
        # The practical gates the finale and the finale does not gate the
        # practical, so this is staged AFTER the exam is scored and refused
        # during it. finale.view refuses too, at the same capability, when
        # there is an encounter to refuse from.
        if path == "/api/finale":
            if self._sealed(g, finale.FINALE_CAPABILITY):
                return True
            report = self._need_dict(body, "exam_report")
            if report is None:
                return True
            return self._reply(g.finale_scene(exam_report=report or None))
        # -- the Standing Portal -------------------------------------------
        # Stepping through changes the world, so it is a POST and it is sealed:
        # the write clause, not the view rule. READING the portal is
        # `/api/portal` above and is never sealed.
        #
        # NOTHING HERE GATES THE PRACTICAL. `/api/interview/start` does not
        # consult this route, this state or the keyring, and
        # `world.portal_gates()` answers False for every measured thing
        # forever. If a future pass makes the exam ask this door for
        # permission, it is a bug, and it is the worst one this file could have.
        if path == "/api/portal/enter":
            if self._sealed(g):
                return True
            return self._reply(g.enter_portal())
        # THE LAST FIGHT, STARTED FROM THE LAST ROOM. The one staged route.
        #
        # It composes the same practical `/api/exam/start` composes and then
        # tells ending.py, by the composed exam's id, that THIS sitting is the
        # story climax. `/api/exam/start` above does not and must never do
        # that: two routes, one of which is the story, is the entire mechanism,
        # and collapsing them is the one change that would break this feature.
        #
        # NOT SEALED, for the same reason `/api/exam/start` is not: this is how
        # a player enters the thing that seals them.
        #
        # AND IT DOES NOT CHECK THE KEYRING. A player who walked in here with
        # the wards dark could not have opened the door, but if they reach this
        # route anyway the exam still runs — `ending.stage()` declines to stage
        # it and the sitting is a measurement. The practical is never behind a
        # door, and a route that refused it would be the worst bug this file
        # could have.
        if path == "/api/portal/trial":
            profile = self._opt_str(body, "profile", "", limit=40)
            if profile is None:
                return True
            if profile and profile not in config.INTERVIEW_PROFILES:
                return self._fail(f"no profile called {profile!r}.", 404)
            return self._reply(g.start_final_trial(profile or None))
        if path == "/api/finale/coda":
            # Bookkeeping: the player watched the second half. Hands over
            # nothing, so it is not sealed.
            return self._reply(g.mark_coda_seen())

        # -- the hunt ------------------------------------------------------
        # Engage and resolve are sealed; FLEE IS NOT, and that asymmetry is the
        # whole of hunters.FLEE_ALWAYS_SUCCEEDS. Walking away costs no gold, no
        # items, no mastery and no roll, turn one included, and a door that
        # could refuse it would be a door that traps a player in a fight they
        # were told they could always leave.
        #
        # `resolve` pays a bounty — gold, metal, a draught and possibly a
        # trophy. The engine does not seal it. Paying a player for a fight
        # during a measured run is the world advancing under the seal, so the
        # door does.
        if path == "/api/hunt/engage":
            if self._sealed(g):
                return True
            region = self._opt_str(body, "region", "", limit=60)
            if region is None or self._region(region) is False:
                return True
            return self._reply(g.hunt_engage(region))
        if path == "/api/hunt/flee":
            return self._reply(g.hunt_flee())
        if path == "/api/hunt/resolve":
            if self._sealed(g):
                return True
            casts = 0
            if body.get("casts") is not None:
                casts = self._need_int(body, "casts", low=0, high=10000)
                if casts is None:
                    return True
            killed = self._need_bool(body, "killed", False)
            if killed is None:
                return True
            return self._reply(g.hunt_resolve(casts=casts, killed=killed))
        return False


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
    # WARM BEFORE THE DOOR OPENS. `game()` builds the Game — and on a cold data
    # directory the whole corpus — on the FIRST REQUEST, which made the first
    # request arbitrarily slow and made `serve()` return a URL that could not
    # be answered for half a minute. launcher.main() already does this in the
    # right order for the shipped app; anything else calling serve() deserves
    # the same order. A caller that has already handed us a Game through
    # set_game() pays nothing here, which is every caller but one.
    #
    # A failure is not fatal: the old lazy path still runs on the first request
    # and reports the error there, which is where it was reported before.
    try:
        game()
    except Exception:                      # noqa: BLE001 - see above
        pass
    httpd = Server(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?t={TOKEN}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, url
