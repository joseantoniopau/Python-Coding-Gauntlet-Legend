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
from . import bestiary, classes, dungeons, finalexam, incantation
from . import pets, progression
from . import quests, saves, worldgen
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
        return self._send(200, target.read_bytes(),
                          ctype or "application/octet-stream", cache=True)

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
        if path == "/api/probes":
            return self._json({"charges": g.probes_remaining()})
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
    # Eleven modules were written, self-checked and unreachable from a browser.
    # Everything below is a thin door onto an engine method that already holds
    # the rules. The server's own two jobs here are input validation — nobody
    # gets a stack trace — and the seal: Interview Mode is refused at the door
    # as well as inside, because a guarantee that only lives three rooms in is
    # one somebody can walk around.
    # ======================================================================
    REGION_IDS = frozenset(r["id"] for r in world.REGIONS)

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
            })

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
    httpd = Server(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/?t={TOKEN}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, url
