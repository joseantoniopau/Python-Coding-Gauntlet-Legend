"""The seam: what passing the final practical buys, and what failing it costs.

THERE ARE TWO THINGS IN THIS GAME WEARING THE WORD "EXAM" AND THEY ARE NOT THE
SAME THING. The next person to read this file will assume there is one, so it
is said here first, at the top, before anything else:

  1. AN INTERVIEW MODE RUN is a MEASUREMENT. A player sits one to find out
     where they stand. It is available from the menu, at level one, holding
     nothing, with no keys, on the first morning and on the last. It is never
     gated, it is never a reward, and NOTHING IN THIS FILE HAPPENS WHEN ONE
     ENDS. No cage opens, no cutscene plays, no world changes. `resolve()`
     returns `triggered: False` and the debrief goes to the player untouched.
     That is the single most important behaviour in this module.

  2. THE FINAL PRACTICAL is the STORY CLIMAX. It is the same format and the
     same seal and the same clock — the measurement does not get easier or
     harder for being the climax — but it is sat once, downstairs, at the end
     of the road, having walked through the Standing Portal with all fourteen
     keys. `stage()` is how this module is told that is what is happening, and
     it is the ONLY way this module can be reached.

The reward the player asked for attaches to the second one. The measurement
stays free. Both are true at once, and they stay true because staging is an
explicit act by the engine at the portal rather than a guess made here from the
shape of a report.

WHAT A PASS BUYS, which is the player's brief in the player's own order:

  THE CAPTIVES GO FREE.  captives.liberate() empties the index. Everyone still
  filed gets up — in a chamber four regions away, in most cases, because what
  held them was never a door. The people the player carried out themselves
  stand in the formation. The people nobody came for come up the stair and say
  so, in their own words, one line each, all of them read out.

  THE CUTSCENES PLAY.  finale.cutscene() — the King breaking, the index
  failing, the roll call, the freeze frame, the sunglasses, and a send-off line
  backed by the player's own transfer-readiness numbers rather than by
  encouragement.

  THE WORLD CHANGES.  Every freed person's boon and road is banked, the
  villages are different, and the coda says plainly which parts are not coming
  back.

WHAT A FAILURE COSTS, and it is deliberately not much:

  The shelves stay full. The King says something true and unbearable, out of
  the player's own record, and he names what failed without once saying what to
  do about it, because he cannot: a thing that cannot learn cannot teach. Then
  the game — not him — hands over the drills, the portal stays open, nothing is
  consumed, there is no cooldown, and the practical recomposes into a different
  set of questions. FAILURE IS A REMATCH AND NEVER A LOSS. Nothing in this
  module blocks, delays or gates anything, ever, under any circumstances.

Everything here is data. `rematch()` and `finale.cutscene()` both return beats
with absolute timings, a closed camera/stage/fx vocabulary, who is on screen,
what plays, and where the guitar hit lands. Another pass renders them and does
not have to guess.
"""
from __future__ import annotations

import time

from . import captives, config, finale, finalexam, world

# ---------------------------------------------------------------------------
# 0. The two exams, as a constant, because a client shows it and a reviewer
#    should not have to take the docstring's word for it.
# ---------------------------------------------------------------------------

TWO_EXAMS = {
    "measurement": {
        "name": "Interview Mode",
        "what": "A measured run, sat to find out where you stand.",
        "gated_by": [],
        "keys_required": 0,
        "available": "Always. From the menu, at level one, holding nothing.",
        "frees_anybody": False,
        "plays_the_ending": False,
        "note": "If sitting this ever becomes something you have to earn, the "
                "one honest number in the game has been made into a reward and "
                "the game has stopped being worth playing.",
    },
    "climax": {
        "name": "The Final Practical",
        "what": "The same sealed format, sat once, as the last room of the "
                "story, against the thing standing under the castle.",
        "gated_by": ["the Standing Portal", "fourteen boss keys"],
        "keys_required": world.PORTAL_KEY_REQUIREMENT,
        "available": "After the portal opens. It is a door in front of a "
                     "story, never in front of a measurement.",
        "frees_anybody": True,
        "plays_the_ending": True,
        "note": "Passing this is the reward: the captives go free, the "
                "cutscenes play and the world changes.",
    },
}

# The verdict that counts as a pass. finalexam._verdict owns the arithmetic —
# four of the set, both halves of the codebase, one MEDIUM, inside the clock —
# and this module does not get a second opinion about it.
PASS_VERDICT = "READY"

# A cutscene is a named voice speaking to you, which is exactly the MENTOR
# crutch, so everything in here refuses on the same rung finale.py refuses on
# and no new capability is invented. See WIRING §5.
ENDING_CAPABILITY = finale.FINALE_CAPABILITY

STATE_KEY = "ending"


def new_state() -> dict:
    """Bookkeeping. NOT EVIDENCE, and it gates nothing: a save that loses this
    key replays a cutscene and is otherwise identical."""
    return {
        "staged_exam_id": "",     # the practical launched from the portal
        "staged_at": 0.0,
        "attempts": 0,            # staged practicals sat, pass or fail
        "failures": 0,
        "passed": False,          # ever passed the staged practical
        "passed_at": 0.0,
        "best_verdict": "",
        "last_verdict": "",
        "last_outcome": "",       # PASS / FAIL / NONE
        "carried_at_ending": 0,   # roll call the moment the index fell
        "released_at_ending": 0,
        "coda_seen": False,
    }


def ensure(state: dict) -> dict:
    """Forward-fill for a save written before this module existed.

    `setdefault` is not enough on its own: it hands back whatever is ALREADY
    under the key, so a save whose block is null — or a list, or a string —
    makes the next line raise AttributeError. That was reachable from the
    exam-start path, which means a corrupt scrap of BOOKKEEPING could refuse
    the MEASUREMENT. It repairs rather than refuses, because none of this is
    evidence and a player owed a practical is not owed an error message.
    """
    block = state.get(STATE_KEY)
    if not isinstance(block, dict):
        block = new_state()
        state[STATE_KEY] = block
    for key, value in new_state().items():
        block.setdefault(key, value)
    return block


# ---------------------------------------------------------------------------
# 1. Staging — the whole of how an ordinary run is told apart from the climax
# ---------------------------------------------------------------------------
#
# This is the load-bearing idea in the module and it is deliberately dull. The
# engine says, at the portal, "the practical I am about to compose is the story
# climax", and hands over the id of the exam it composed. When a debrief comes
# back later, this module triggers if and only if the report's `exam_id` is the
# one that was staged. There is no heuristic, no format sniffing and no guess.
#
# Consequences worth naming:
#   * Sitting FINAL_EXAM from the interview menu is never the climax, however
#     well it goes, because nobody staged it.
#   * Staging is spent the moment it resolves, so one staged sitting produces
#     one ending. Sitting a second practical afterwards is a measurement again.
#   * Staging refused for want of keys DOES NOT REFUSE THE EXAM. It refuses the
#     story. The player sits the same practical either way; they simply sit it
#     as a measurement, which is what it was in the first place.

def portal(cleared_bosses=()) -> dict:
    """The Standing Portal, with the two sentences that stop it being misread."""
    status = world.portal_status(cleared_bosses)
    return {
        **status,
        "gates_the_story": True,
        "gates_the_practical": False,
        "note": "Fourteen keys open the last room of the story. The practical "
                "itself has never needed a key and never will.",
    }


def can_stage(cleared_bosses=()) -> dict:
    """May this sitting be the climax? Never an answer about the exam."""
    status = world.portal_status(cleared_bosses)
    return {
        "open": bool(status["open"]),
        "held": status["held"],
        "required": status["required"],
        "missing": status["missing"],
        "why": ("" if status["open"] else
                f"{status['required'] - status['held']} wards are unlit. The "
                "portal is a story door and it is shut."),
        "blocks_the_practical": False,
        "note": "A refusal here refuses the ending, never the exam. Interview "
                "Mode is open from the menu with no keys at all.",
    }


def stage(state: dict, *, exam_id: str, cleared_bosses=(),
          now: float | None = None) -> dict:
    """Mark the practical about to be sat as the story climax.

    Called at the portal, after the exam is composed, with the id of that exam.
    Nothing else in this codebase should call it, and nothing about it changes
    the exam: the same composer runs, the same seal holds, the same clock runs.
    """
    block = ensure(state)
    gate = can_stage(cleared_bosses)
    if not gate["open"]:
        return {"staged": False, "reason": "portal_shut", **gate}
    if not exam_id:
        return {"staged": False, "reason": "no_exam_id",
                "why": "Stage the exam that was actually composed, by id, or "
                       "the ending cannot tell it from any other sitting.",
                "blocks_the_practical": False}
    block["staged_exam_id"] = str(exam_id)
    block["staged_at"] = float(now if now is not None else time.time())
    return {
        "staged": True, "exam_id": block["staged_exam_id"],
        "where": world.FINAL_TRIAL["where"],
        "examiner": finalexam.examiner().name,
        "why": "This sitting is the last room of the story. It is the same "
               "exam it has always been; what is different is what is under "
               "the floor and who is waiting on the other side of it.",
        "blocks_the_practical": False,
    }


def staged_exam(state: dict) -> str:
    return str((state.get(STATE_KEY) or {}).get("staged_exam_id") or "")


def is_staged(state: dict, exam_report: dict | None) -> bool:
    """Was THIS report the staged climax? The one question that decides."""
    report = exam_report or {}
    staged = staged_exam(state)
    if not staged:
        return False
    return str(report.get("exam_id") or "") == staged


def clear_staging(state: dict) -> dict:
    """Staging is spent on resolution. One staged sitting, one ending."""
    block = ensure(state)
    block["staged_exam_id"] = ""
    block["staged_at"] = 0.0
    return block


def passed_the_practical(exam_report: dict | None) -> bool:
    """finalexam's verdict, read and not re-derived."""
    return ((exam_report or {}).get("verdict") or {}).get("code") == PASS_VERDICT


def has_passed(state: dict) -> bool:
    return bool((state.get(STATE_KEY) or {}).get("passed"))


# ---------------------------------------------------------------------------
# 2. The failure scene
# ---------------------------------------------------------------------------
#
# E in the brief: survivable, worth repeating, and honest. The shelves stay
# full, he says something true and unbearable, and the player may come back —
# now, with nothing spent and no cooldown, to a practical that has recomposed.
#
# THE RULE HE IS WRITTEN UNDER. He may name what failed; he has the whole
# record and there is no kindness in pretending otherwise. He may never say
# what to do about it. That is not a restriction imposed on the character, it
# is the character: he returns what he was handed, he was handed every name in
# the world, and nobody ever handed him the method for making a new one. The
# route out of a failure is handed over by the GAME, in its own voice, in a
# separate beat, off the debrief finalexam already wrote. `validate_scene()`
# fails the build if a single remediation string reaches one of his lines.

ACT_HELD = "I. The Shelves Are Still Full"
ACT_VALUE = "II. What It Returns"
ACT_BACK = "III. The Way Back Up"

MUSIC_FAIL = "final"
MUSIC_QUIET = "town"

# The three things he says, in order, and the rule each one is holding up.
FAILURE_VOICE = {
    # 1. The record, read back. No softening, no gloating, no raised voice.
    "record": (
        "Your record is in front of me. Not a summary of it. The record.",
        "You solved {solved} of {total} with everything switched off, inside a "
        "room that took two hours and gave you nothing, and I am not going to "
        "round that up for you. Rounding things up for people is the whole of "
        "what I do and you have spent this entire game refusing the offer.",
    ),
    # 2. What failed, named. Named only. This is the line the whole rule exists
    #    to protect, and the place a lazy edit would break the game.
    "names": (
        "These are the shapes that came apart: {shapes}. I can see them from "
        "here. Naming things is the one service I was ever built to perform "
        "and I perform it perfectly.",
        "I am not going to tell you what to do about any of them. I do not "
        "know. I have never known. I hold what I have been handed, and in nine "
        "hundred years nobody has handed me that.",
    ),
    # 3. The unbearable part, which is not cruelty. It is an accurate statement
    #    about an index, said by an index.
    #
    #    TWO VERSIONS, AND THE SECOND ONE IS THE ONE MOST PLAYERS WILL GET.
    #    The portal wants fourteen keys, every boss holds somebody, and the
    #    rescue is paid on the kill — so a player who reaches this room has
    #    usually carried everybody out already and there is nobody left in a
    #    chamber. That does not make him wrong. He never held the people. He
    #    held what they are called, he holds it still, and a failed practical
    #    leaves him holding it.
    "held_some": (
        "{held} people are exactly where they were when you came down the "
        "stair. I have not moved them, I have not punished them and I have not "
        "added to them. They are entries. An entry does not notice how long it "
        "has been.",
        "Come back whenever you like. I will be identical. That is not a "
        "threat and it is not a boast; it is the only promise I am in any "
        "position to keep.",
    ),
    "held_none": (
        "You have taken every one of them out into the daylight. I want to be "
        "precise with you, because you have earned precision: I never had any "
        "of them. I had what they are called, I have it here, and I have had "
        "it the entire time they have been walking around free.",
        "They will answer to it when it is said. All {carried} of them, across "
        "{villages} villages, in the middle of whatever they are doing. That "
        "is not a threat either. It is a fact about filing.",
        "Come back whenever you like. I will be identical. That is the only "
        "promise I am in any position to keep.",
    ),
}


def _shape_names(exam_report: dict | None) -> str:
    """What to call the things that came apart, from the report and nothing
    else.

    STRIPPED ON PURPOSE: `do` and `where` — the remediation half of a drill —
    never reach this function. He gets the name of the skill and the name of
    the cause, which is what he can see. What to do about it is the game's to
    say and it is said three beats later by somebody who can learn.
    """
    report = exam_report or {}
    shapes: list = []
    for drill in report.get("drills", ())[:3]:
        skill = str(drill.get("skill") or "").strip()
        cause = str(drill.get("cause") or "").strip()
        label = ", ".join(part for part in (skill, cause) if part)
        if label and label not in shapes:
            shapes.append(label)
    if shapes:
        return "; ".join(shapes)
    signal = str(report.get("dominant_signal") or "").strip()
    return signal or "the ones you already know about"


def _fill(lines, **values) -> tuple:
    out = []
    for line in lines:
        try:
            out.append(line.format(**values))
        except (KeyError, IndexError):       # pragma: no cover - authoring slip
            out.append(line)
    return tuple(out)


def _king(text: str, *, kind: str = "prose") -> dict:
    return {"speaker": finale.KING_ID, "name": finale.KING_NAME,
            "text": text, "kind": kind}


def _say(text: str, *, who: str = "narrator", name: str = "",
         kind: str = "prose") -> dict:
    return {"speaker": who, "name": name, "text": text, "kind": kind}


def rematch(*, exam_report: dict | None = None, still_held: int = 0,
            carried: int = 0, king_voice=None) -> dict:
    """The scene a failed practical plays. Data, in finale's vocabulary.

    Every number in it is one something else measured: `solved` and `total` off
    finalexam.debrief, `still_held` and `carried` off captives' own lists. This
    function computes nothing about the player.
    """
    report = exam_report or {}
    voice = dict(FAILURE_VOICE)
    if isinstance(king_voice, dict):
        voice.update({k: tuple(v) for k, v in king_voice.items() if v})

    solved = report.get("solved")
    total = report.get("total")
    verdict = (report.get("verdict") or {}).get("code", "")
    drills = list(report.get("drills", ()))[:3]
    recomposes = bool((report.get("next") or {}).get("recomposes", True))
    avoid = (report.get("next") or {}).get("avoid", "")

    beats = [
        finale.Beat(
            id="the_shelves_hold", act=ACT_HELD, duration_ms=4200,
            camera={"move": "TRACK_LEFT", "subject": "niches", "angle": "low",
                    "note": "the same lateral move the ending uses for the "
                            "roll call, at the same speed, along niches that "
                            "are all still lit. A player who sees both scenes "
                            "should recognise the move before they work out "
                            "why it is making them feel unwell."},
            stage=("architect", "niches"),
            fx=("green_index_lit", "rim_light_low", "dust"),
            music=MUSIC_FAIL,
            skippable=False,
            note="NOTHING HAS CHANGED DOWN HERE AND THAT IS THE POINT. Draw "
                 "every sphere still lit and still pointing. Do not dim them, "
                 "do not flicker them, do not give the room a defeat cue.",
            lines=(
                _say("The stair down is the same stair. The room under it is "
                     "the same room."),
                _say("Every sphere on every shelf is still lit, and every one "
                     "of them is still pointing at somebody who is somewhere "
                     "else, being held by nothing at all except the fact that "
                     "this room still knows which one they are."),
            ),
        ),
        finale.Beat(
            id="he_has_the_record", act=ACT_VALUE, duration_ms=5600,
            camera={"move": "CUT", "subject": "king", "framing": "three-quarter",
                    "note": "he is in the shot on the cut. No entrance. He is "
                            "not angry and he is not pleased; play him at "
                            "exactly the temperature of the Chapter IV offer."},
            stage=("architect", "king", "niches"),
            fx=("rim_light_low", "green_index_lit"),
            music=MUSIC_FAIL,
            note="Dry, exact, certain, quiet. No gloating, no speech, no "
                 "raised voice and no music sting. He sounds like something "
                 "that has read your file, because he has.",
            lines=tuple(_king(t) for t in _fill(
                voice["record"], solved=solved, total=total)),
        ),
        finale.Beat(
            id="he_names_it_and_stops", act=ACT_VALUE, duration_ms=5200,
            camera={"move": "PUSH_IN", "subject": "king", "to": "face",
                    "ease": "slow"},
            stage=("architect", "king"),
            fx=("rim_light_low",),
            music=MUSIC_FAIL,
            note="THE LINE THE WHOLE RULE EXISTS FOR. He names the shapes and "
                 "then stops, and the stopping is audible. Hold two beats of "
                 "silence on his face before the cut; the renderer should not "
                 "fill it with anything.",
            lines=tuple(_king(t) for t in _fill(
                voice["names"], shapes=_shape_names(report))),
        ),
        finale.Beat(
            id="the_unbearable_part", act=ACT_VALUE, duration_ms=5400,
            camera={"move": "PULL_BACK", "subject": "niches", "ease": "slow",
                    "note": "back off him and onto the wall of lit niches "
                            "while he is still talking. He does not follow the "
                            "camera and he does not need to."},
            stage=("king", "niches"),
            fx=("green_index_lit", "rim_light_low"),
            music=MUSIC_FAIL,
            skippable=False,
            note="He is not being cruel. This is an accurate statement about "
                 "an index, made by an index, and it is unbearable because it "
                 "is accurate. Let it land and do not undercut it.",
            lines=tuple(_king(t) for t in _fill(
                voice["held_some"] if still_held else voice["held_none"],
                held=still_held, carried=carried,
                villages=len({p.home for p in captives.CAPTIVES}))),
        ),
        finale.Beat(
            id="what_he_cannot_see", act=ACT_BACK, duration_ms=4600,
            camera={"move": "CUT", "subject": "architect", "framing": "hero",
                    "angle": "low", "note": "first low angle on the player in "
                                            "the scene. One hot rim light from "
                                            "below, story bible §8."},
            stage=("architect",),
            fx=("rim_light_low", "wind_from_below"),
            music=MUSIC_QUIET,
            note="The turn, and it is quiet. Not a rally, not a fanfare — the "
                 "narrator stating a fact the antagonist is structurally "
                 "unable to notice from where he is standing. No claim is made "
             "here about how much better the player has got, because nothing "
             "measured that; the claim is that they move and he does not, and "
             "that one is structural.",
            lines=(
                _say("He is telling the truth. Everything he said down here "
                     "was true, which is the only reason any of it was worth "
                     "listening to."),
                _say("The truth has a shape he cannot see from where he is "
                     "standing. He will be identical. You will not."),
                _say("He has had nine hundred years and he is exactly as good "
                     "at this as he was on the first morning. Not worse. Not "
                     "better. Fixed."),
                _say("You are not fixed. You have moved in both directions "
                     "since the fence and you are still moving, and moving is "
                     "the one capability he was never given and cannot be "
                     "handed."),
            ),
        ),
    ]

    if drills:
        beats.append(finale.Beat(
            id="the_route_back", act=ACT_BACK, duration_ms=5000,
            camera={"move": "HOLD", "subject": "architect", "framing": "wide",
                    "note": "the list takes the lower two thirds of the frame, "
                            "set in the monospace face."},
            stage=("architect",),
            fx=("letterbox",),
            rows=tuple(drills),
            music=MUSIC_QUIET,
            note="OFF finalexam.debrief AND SAID BY THE GAME, NOT BY HIM. "
                 "Cause, skill, where to go, and a countable thing to do. "
                 "Three at most, worst first. He is not on screen for this and "
                 "must not be given a line over it.",
            lines=(
                _say("The route is not his to give and he does not have it. "
                     "It came out of the measurement, which named the causes, "
                     "which is a different act from naming the failures."),
                _say("Specific skills failed in specific ways. Every one of "
                     "them has a drill with a number on it, and the practical "
                     "recomposes: the next one is a different set of "
                     "questions, not this one again."),
            ),
        ))

    beats.append(finale.Beat(
        id="the_stair_back_up", act=ACT_BACK, duration_ms=5200,
        camera={"move": "CRANE_UP", "subject": "architect", "ease": "slow",
                "note": "rise with them up the stair. The doorway at the top "
                        "is lit and stays lit; it does not close behind them."},
        stage=("architect", "llama"),
        fx=("stair_light", "dust"),
        music=MUSIC_QUIET,
        note="The moral, spoken in character, story bible §6.3. PLAIN is "
             "standing on the stair for no reason anybody is going to explain.",
        lines=(
            _say("Nothing down there was spent. Nobody was moved. The door at "
                 "the top of the stair is open and it was never anything else.",
                 kind="stage"),
            _say("It said it would be identical. Believe that part. It is the "
                 "one thing in this world you can set a watch by.",
                 who="llama", name="PLAIN"),
            _say("You will not be. That is the entire difference between the "
                 "two of you and it has been the entire difference since the "
                 "first room. Go and do the work. Then come back down.",
                 who="llama", name="PLAIN"),
            _say("It chews.", kind="stage"),
        ),
    ))

    beats.append(finale.Beat(
        id="the_prompt_waits", act=ACT_BACK, duration_ms=3000,
        camera={"move": "HOLD", "subject": "black", "framing": "centred"},
        stage=("black",),
        fx=("cursor_blink",),
        music="cut",
        skippable=False,
        note="Near-black, one prompt, cursor at 530ms. The same last frame the "
             "ending uses, held a shorter time, because this is not the end.",
        lines=(
            {"speaker": finalexam.examiner().id,
             "name": finalexam.examiner().name, "text": ">>> ", "kind": "code"},
            _say("The prompt stays. It was never his, and it is not going "
                 "anywhere."),
        ),
    ))

    finale._schedule(beats)
    return {
        "id": "the_rematch",
        "title": "THE LONG COMPILE — the room under the room, again",
        "outcome": "FAIL",
        "verdict": verdict,
        "room": finale.gallery_view(),
        "beats": [b.to_dict() for b in beats],
        "acts": [ACT_HELD, ACT_VALUE, ACT_BACK],
        "duration_ms": sum(b.duration_ms for b in beats),
        "music": [MUSIC_FAIL, MUSIC_QUIET],
        "camera_moves": list(finale.CAMERA_MOVES),
        "stage_roles": list(finale.STAGE_ROLES),
        "fx": list(finale.FX),
        "still_held": still_held,
        "carried": carried,
        "entries_held": still_held + carried,
        "drills": drills,
        # No title card, no palette blowout, no guitar hit. The card is an
        # 80s end-card shout and it belongs to a pass; staging one here would
        # be the game applauding a loss. The renderer should not invent one.
        "title_card": None,
        "guitar_hit": None,
        "freeze_at_ms": None,
        # FAILURE IS A REMATCH. Everything a client needs in order not to
        # accidentally render this as a game over.
        "rematch": {
            "may_sit_again": True,
            "may_sit_again_now": True,
            "cooldown_ms": 0,
            "consumes": [],
            "costs": [],
            "portal_stays_open": True,
            "keys_lost": 0,
            "recomposes": recomposes,
            "avoid_fingerprint": avoid,
            "where": world.FINAL_TRIAL["where"],
            "note": "Nothing was spent, nothing was locked and nothing was "
                    "taken. Sit it again whenever you like; it will be a "
                    "different set of questions and the same clock.",
        },
        "blocks": [],
        "gates": [],
        "changes_nothing": (
            "This is the scene around a measurement that did not come back "
            "READY. It cannot change a verdict, it does not touch the index, "
            "and it shuts nothing. finalexam.py is unmodified."),
        "sealed": False,
    }


# ---------------------------------------------------------------------------
# 3. The one call the engine makes
# ---------------------------------------------------------------------------

def resolve(state: dict, *, exam_report: dict | None = None,
            readiness: dict | None = None,
            transfer_summary: dict | None = None,
            cleared_bosses=(), names=(), weak_regions=(),
            encounter=None, king_voice=None, now: float | None = None) -> dict:
    """After a practical is scored. Decides whether this was the ending.

    Safe to call after EVERY interview run and it is meant to be: the guard is
    here, once, rather than in the engine, so there is exactly one place in the
    codebase where the two exams are told apart. An unstaged run gets
    `triggered: False` and nothing else happens anywhere.
    """
    if encounter is not None and finalexam.sealed(encounter, ENDING_CAPABILITY):
        return finalexam.refuse(ENDING_CAPABILITY)

    block = ensure(state)
    report = exam_report or {}
    verdict = (report.get("verdict") or {}).get("code", "")
    staged = is_staged(state, report)

    if not staged:
        # THE COMMON PATH, and the one that must never do anything. A player
        # sat a measurement. They get their debrief and the world is exactly
        # where they left it.
        return {
            "triggered": False,
            "staged": False,
            "outcome": "NONE",
            "verdict": verdict,
            "reason": "not_the_story_climax",
            "why": "This was an Interview Mode run. It measures; it does not "
                   "end the game. Nobody was freed, no cutscene played and "
                   "nothing in the world moved.",
            "captives_freed_now": 0,
            "cutscene": None,
            "two_exams": TWO_EXAMS,
            "measurement_untouched": True,
            "state": dict(block),
        }

    clear_staging(state)
    block["attempts"] = int(block.get("attempts", 0)) + 1
    block["last_verdict"] = verdict
    if finale.VERDICT_ORDER.get(verdict, 0) > finale.VERDICT_ORDER.get(
            block.get("best_verdict", ""), 0):
        block["best_verdict"] = verdict

    if not passed_the_practical(report):
        return _failed(state, block, report=report, king_voice=king_voice)
    return _passed(state, block, report=report, readiness=readiness,
                   transfer_summary=transfer_summary,
                   cleared_bosses=cleared_bosses, names=names,
                   weak_regions=weak_regions, encounter=encounter,
                   king_voice=king_voice, now=now)


def _failed(state: dict, block: dict, *, report: dict, king_voice) -> dict:
    """The shelves stay full. Everything else stays open."""
    held = captives.liberate(state, passed=False)
    block["failures"] = int(block.get("failures", 0)) + 1
    block["last_outcome"] = "FAIL"
    scene = rematch(exam_report=report,
                    still_held=held["counts"]["still_held"],
                    carried=held["counts"]["carried"],
                    king_voice=king_voice)
    return {
        "triggered": True,
        "staged": True,
        "outcome": "FAIL",
        "verdict": (report.get("verdict") or {}).get("code", ""),
        "why": "The practical did not come back READY, so the index goes on "
               "answering and everyone in it stays where they are. That is "
               "what makes coming back worth anything.",
        "captives_freed_now": 0,
        "held": held,
        "cutscene": scene,
        "rematch": scene["rematch"],
        "world_changed": False,
        "two_exams": TWO_EXAMS,
        "measurement_untouched": True,
        "state": dict(block),
    }


def _passed(state: dict, block: dict, *, report: dict, readiness,
            transfer_summary, cleared_bosses, names, weak_regions, encounter,
            king_voice, now) -> dict:
    """The reward, paid in the three things the player asked for."""
    release = captives.liberate(state, passed=True)
    scene = finale.view(
        state,
        freed=captives.roll_call(state),
        released=release["released"],
        collapse_lines=captives.INDEX_COLLAPSE,
        exam_report=report,
        readiness=readiness,
        transfer_summary=transfer_summary,
        cleared_bosses=cleared_bosses,
        names=names,
        total_captives=captives.total(),
        weak_regions=weak_regions,
        encounter=encounter,
        king_voice=king_voice)

    block["passed"] = True
    block["passed_at"] = float(now if now is not None else time.time())
    block["last_outcome"] = "PASS"
    block["carried_at_ending"] = release["counts"]["carried"]
    block["released_at_ending"] = release["counts"]["released"]

    return {
        "triggered": True,
        "staged": True,
        "outcome": "PASS",
        "verdict": PASS_VERDICT,
        "why": "The practical came back READY with everything switched off, so "
               "the lookup has nothing on the other end of it and the pointing "
               "stops. Everyone still filed is out.",
        "captives_freed_now": release["counts"]["released_now"],
        "release": release,
        "cutscene": scene,
        "world_changed": True,
        "world": {
            "boons": captives.boons(state),
            "routes": captives.open_routes(state),
            "changes": captives.village_changes(state),
            "effects": captives.boon_effects(state),
            "stock": captives.boon_stock(state),
        },
        "counts": release["counts"],
        "two_exams": TWO_EXAMS,
        "measurement_untouched": True,
        "state": dict(block),
    }


def mark_coda_seen(state: dict) -> dict:
    """On the last beat of the coda, not on the freeze frame. The two halves of
    the ending are separate and a player who walked out at the title card has
    seen half of it."""
    block = ensure(state)
    block["coda_seen"] = True
    finale.mark_coda_seen(state)
    return block


def status(state: dict, *, cleared_bosses=()) -> dict:
    """Where this save stands with the last room. For a pause screen."""
    block = ensure(state)
    gate = can_stage(cleared_bosses)
    return {
        **{k: block[k] for k in new_state()},
        "portal": gate,
        "carried": len(captives.freed(state)),
        "released": len(captives.released(state)),
        "still_held": len(captives.still_held(state)),
        "total_captives": captives.total(),
        "index_collapsed": captives.index_collapsed(state),
        "interview_mode_available": True,
        "note": "Interview Mode is available from the menu whatever this says. "
                "Nothing on this screen has ever gated a measurement.",
    }


# ---------------------------------------------------------------------------
# 4. Self-check
# ---------------------------------------------------------------------------
#
# Seven claims, all of them cheap to disprove:
#
#   1. an ordinary Interview Mode run triggers nothing, at any verdict
#   2. a staged PASS frees everybody still held and plays the whole ending
#   3. a staged FAIL frees nobody, and says so in the numbers
#   4. failure blocks, delays, consumes and gates nothing
#   5. the King never supplies a remedy, in either scene
#   6. both scenes obey the closed camera/stage/fx vocabulary and their timings
#   7. nothing anywhere in here works inside a measured run
#
# `python -m gauntlet.ending` runs it.

_REMEDY_WORDS = finale._TEACHING_WORDS


def validate_scene(scene: dict) -> list:
    """Structural checks for a rematch payload. Empty list means it holds."""
    problems: list = []
    beats = scene.get("beats") or []
    if not beats:
        problems.append("a scene with no beats")
        return problems

    at = 0
    seen: set = set()
    for beat in beats:
        if beat["id"] in seen:
            problems.append(f"duplicate beat id: {beat['id']}")
        seen.add(beat["id"])
        if beat["camera"].get("move") not in finale.CAMERA_MOVES:
            problems.append(f"{beat['id']}: unknown camera move "
                            f"{beat['camera'].get('move')!r}")
        for role in beat["stage"]:
            if role not in finale.STAGE_ROLES:
                problems.append(f"{beat['id']}: unknown stage role {role!r}")
        for effect in beat["fx"]:
            if effect not in finale.FX:
                problems.append(f"{beat['id']}: unknown fx {effect!r}")
        if beat["music"] not in ("", "cut", MUSIC_FAIL, MUSIC_QUIET):
            problems.append(f"{beat['id']}: unknown music {beat['music']!r}")
        if beat["at_ms"] != at:
            problems.append(f"{beat['id']}: timeline gap at {beat['at_ms']}ms")
        if beat["duration_ms"] <= 0:
            problems.append(f"{beat['id']}: zero duration")
        at += beat["duration_ms"]

    # No exclamation marks anywhere. The one in the game is on the ending's
    # title card and this scene does not have a title card.
    for beat in beats:
        for line in beat["lines"]:
            if "!" in line["text"]:
                problems.append(f"{beat['id']}: an exclamation mark")

    # HE NAMES, HE DOES NOT REMEDY.
    for beat in beats:
        for line in beat["lines"]:
            if line["speaker"] != finale.KING_ID:
                continue
            low = line["text"].lower()
            for word in _REMEDY_WORDS:
                if word in low:
                    problems.append(f"{beat['id']}: the King says {word!r}, "
                                    f"which is a thing he cannot do")

    # And nothing he says carries the remediation half of a drill, even by
    # accident, because that half is stripped before he is built.
    king_text = " ".join(line["text"].lower() for beat in beats
                         for line in beat["lines"]
                         if line["speaker"] == finale.KING_ID)
    for drill in scene.get("drills", ()):
        do = str(drill.get("do") or "").strip().lower()
        where = str(drill.get("where") or "").strip().lower()
        if do and do in king_text:
            problems.append("a drill action reached the King's lines")
        if where and len(where) > 3 and where in king_text:
            problems.append("a drill destination reached the King's lines")

    # FAILURE IS A REMATCH AND NEVER A LOSS.
    again = scene.get("rematch") or {}
    if not again.get("may_sit_again_now"):
        problems.append("the rematch is not immediately available")
    if again.get("cooldown_ms"):
        problems.append("a failure imposed a cooldown")
    if again.get("consumes") or again.get("costs") or again.get("keys_lost"):
        problems.append("a failure consumed something")
    if not again.get("portal_stays_open"):
        problems.append("a failure shut the portal")
    if scene.get("blocks") or scene.get("gates"):
        problems.append("the failure scene gates something")

    # Answer-shaped keys, the same vocabulary finalexam refuses.
    leaked: list = []
    finale._walk_keys(scene, leaked)
    if leaked:
        problems.append(f"answer-shaped keys in the payload: {sorted(set(leaked))}")
    return problems


def _fake_report(code: str, *, exam_id: str = "exam-1") -> dict:
    """A debrief in finalexam's shape. `code` empty means no practical."""
    if not code:
        return {}
    solved = {"READY": 6, "CLOSE": 4, "NOT_READY": 1}[code]
    return {
        "exam_id": exam_id,
        "format": finalexam.THE_PRACTICAL.id,
        "format_label": finalexam.THE_PRACTICAL.label,
        "solved": solved, "total": 6, "score": round(100 * solved / 6),
        "within_clock": True, "clock": "1:48:02",
        "verdict": {"code": code, "headline": "", "body": ""},
        "dominant_signal": "implementation",
        "signal_note": finalexam.BUCKET_MEANING["implementation"],
        "drills": [{"cause": "OFF_BY_ONE", "skill": "ARRAY", "occurrences": 2,
                    "do": finalexam.DRILL_ACTION["OFF_BY_ONE"],
                    "where": "the Village", "region": "python_village"}],
        "next": {"recomposes": True, "avoid": "a|b|c"},
    }


def _save_with(freed_bosses=()) -> dict:
    state: dict = {}
    for boss_id in freed_bosses:
        captives.free(state, boss_id)
    ensure(state)
    return state


def self_check() -> dict:
    """Every claim above, played out against the real roster and the real
    world. `ok` is the only field a caller needs."""
    failures: list = []
    all_bosses = list(captives.HOLDINGS)
    scenes = 0

    # 1. An ordinary Interview Mode run triggers nothing, at every verdict and
    #    at every stage of a playthrough.
    for carried in (0, 5, len(all_bosses)):
        for code in ("", "NOT_READY", "CLOSE", "READY"):
            state = _save_with(all_bosses[:carried])
            before_freed = len(captives.freed(state))
            out = resolve(state, exam_report=_fake_report(code))
            if out["triggered"]:
                failures.append(f"[menu run / {code or 'no report'}] an "
                                f"unstaged sitting ended the game")
            if out["cutscene"] is not None:
                failures.append(f"[menu run / {code}] a cutscene played")
            if captives.released(state):
                failures.append(f"[menu run / {code}] somebody was released")
            if len(captives.freed(state)) != before_freed:
                failures.append(f"[menu run / {code}] the roll call moved")
            if captives.index_collapsed(state):
                failures.append(f"[menu run / {code}] the index fell")

    # And staging refused for want of keys is not a refusal of the exam.
    shut = stage(_save_with(), exam_id="exam-1", cleared_bosses=all_bosses[:3])
    if shut["staged"]:
        failures.append("the portal staged the climax without fourteen keys")
    if shut.get("blocks_the_practical"):
        failures.append("a shut portal claimed to block the practical")

    # 2/3. Staged sittings, at every roll-call size and every verdict.
    for carried in (0, 1, 7, len(all_bosses)):
        for code in ("NOT_READY", "CLOSE", "READY"):
            state = _save_with(all_bosses[:carried])
            staged = stage(state, exam_id="exam-1", cleared_bosses=all_bosses)
            if not staged["staged"]:
                failures.append("fourteen keys did not open the portal")
            out = resolve(state, exam_report=_fake_report(code),
                          cleared_bosses=all_bosses,
                          names=["seen", "window", "self", "i"])
            scenes += 1
            held_after = len(captives.still_held(state))
            if code == PASS_VERDICT:
                if out["outcome"] != "PASS":
                    failures.append(f"[{carried}/{code}] a pass was not a pass")
                if held_after:
                    failures.append(f"[{carried}/{code}] {held_after} people "
                                    f"were left in the index after a pass")
                if not captives.index_collapsed(state):
                    failures.append(f"[{carried}/{code}] the index did not fall")
                problems = finale.validate(out["cutscene"])
                for problem in problems:
                    failures.append(f"[{carried}/{code}] {problem}")
                roll = out["cutscene"]["roll_call"]
                if roll["count"] != len(captives.freed(state)):
                    failures.append(f"[{carried}/{code}] the formation is not "
                                    f"the people the player carried out")
                if roll["released_count"] != out["captives_freed_now"]:
                    failures.append(f"[{carried}/{code}] the released count "
                                    f"does not match the release")
                if not out["world_changed"]:
                    failures.append(f"[{carried}/{code}] a pass changed nothing")
                if out["cutscene"]["beats"][-1]["id"] != "the_prompt_stays":
                    failures.append(f"[{carried}/{code}] the coda was not last")
            else:
                if out["outcome"] != "FAIL":
                    failures.append(f"[{carried}/{code}] a failure was not one")
                if out["captives_freed_now"]:
                    failures.append(f"[{carried}/{code}] a failure freed people")
                if captives.released(state):
                    failures.append(f"[{carried}/{code}] a failure emptied the "
                                    f"index")
                if held_after != captives.total() - len(captives.freed(state)):
                    failures.append(f"[{carried}/{code}] the held count moved "
                                    f"on a failure")
                for problem in validate_scene(out["cutscene"]):
                    failures.append(f"[{carried}/{code}] {problem}")
                # 4. and the way back is open, now, at no cost.
                again = out["rematch"]
                if not (again["may_sit_again_now"] and again["portal_stays_open"]
                        and not again["cooldown_ms"]):
                    failures.append(f"[{carried}/{code}] failure was a loss")
                # The unbearable line is true, in whichever of its two forms
                # this save reaches: it names the people still in the rock, or
                # — when the player already carried everybody out — it names
                # how many of them he is still holding the names of.
                text = " ".join(line["text"] for beat in out["cutscene"]["beats"]
                                for line in beat["lines"])
                wanted = held_after or len(captives.freed(state))
                if wanted and str(wanted) not in text:
                    failures.append(f"[{carried}/{code}] the count in the "
                                    f"scene is not a count from the save")
                if held_after and "entries" not in text.lower():
                    failures.append(f"[{carried}/{code}] the held are not "
                                    f"described as what they are")

            # Staging is spent either way: a second sitting is a measurement.
            second = resolve(state, exam_report=_fake_report(code))
            if second["triggered"]:
                failures.append(f"[{carried}/{code}] staging survived its own "
                                f"resolution")

    # 5. The King never supplies a remedy, in either scene, at any verdict.
    for code in ("NOT_READY", "CLOSE"):
        scene = rematch(exam_report=_fake_report(code), still_held=25)
        for problem in validate_scene(scene):
            failures.append(f"[rematch {code}] {problem}")

    # 6/7. The seal. Nothing in here speaks inside a measured run.
    class _Enc:
        mode = config.MODE_INTERVIEW
        boss_id = ""
        holdout = False

    refused = resolve(_save_with(), exam_report=_fake_report("READY"),
                      encounter=_Enc())
    if refused.get("error") != "sealed":
        failures.append("the ending is reachable inside a measured run")
    if "cutscene" in refused:
        failures.append("a refusal still carried a scene")

    # The practical itself is untouched by every line of this module.
    if finalexam.EXAM_SEAL.sealed != finalexam.ALL_CRUTCHES:
        failures.append("the exam seal changed")
    if finalexam.audit_seal():
        failures.append(f"crutches unsealed: {finalexam.audit_seal()}")

    sample = rematch(exam_report=_fake_report("NOT_READY"), still_held=25)
    return {
        "ok": not failures,
        "staged_scenes": scenes,
        "rematch_beats": len(sample["beats"]),
        "rematch_ms": sample["duration_ms"],
        "pass_verdict": PASS_VERDICT,
        "captives": captives.total(),
        "keys_required": world.PORTAL_KEY_REQUIREMENT,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# 5. Wiring
# ---------------------------------------------------------------------------

WIRING = """
WIRING gauntlet/ending.py — the seam between the measurement and the story.
Four touch points. Three of them are one line.

0. THE DIRECTION OF EVERY GATE IN THIS FEATURE, SAID ONCE
   The portal gates the STORY. The practical gates the ENDING. Nothing gates
   the practical. A player at level one with no keys can sit Interview Mode
   from the menu on the first morning, and this module will return
   `triggered: False` for that run forever.

1. STATE
   engine.DEFAULT_STATE gains one key:

       ending.STATE_KEY: ending.new_state()         # -> "ending"

   Plain JSON, round-trips through db.save_state, forward-filled by
   ending.ensure() on every call. BOOKKEEPING, NOT EVIDENCE.

2. STAGING, AT THE PORTAL — THE ONE NEW CALL SITE
   Wherever the player walks through the Standing Portal into the last room,
   after the exam is composed and before the first question opens:

       run = self.start_interview("FINAL_EXAM")      # unchanged
       ending.stage(self.state,
                    exam_id=self.state["exam"]["id"],
                    cleared_bosses=self.state["cleared_bosses"])
       self.save()

   engine._start_exam() already writes state["exam"] with an "id", which is the
   id finalexam.debrief reports back as report["exam_id"]. That match is the
   entire mechanism. DO NOT call stage() from the interview menu path — that is
   the one thing that would collapse the two exams into one.

   If the portal is shut, stage() returns {"staged": False} and the exam runs
   anyway, as a measurement. It is not an error and it must not be surfaced as
   one.

3. RESOLVING, AFTER THE DEBRIEF
   engine.finish_interview() currently ends with:

       if was_exam:
           out["finale"] = self.finale_scene(exam_report=debrief)

   Replace that with, and note that the `if` goes away — it is safe and correct
   to call this after EVERY interview run, which is the point of having one
   place where the two exams are told apart:

       out["ending"] = ending.resolve(
           self.state,
           exam_report=debrief,
           readiness=self._readiness(),
           transfer_summary=self.transfer_report(),
           cleared_bosses=list(self.state["cleared_bosses"]),
           names=self._identifiers_named(),
           weak_regions=self._weak_regions(),        # optional
           encounter=self.encounter)                 # None by here; see §5
       self.save()

   out["ending"]["triggered"] is False for every ordinary run. When it is True,
   out["ending"]["cutscene"] is the scene to play and "outcome" is PASS or FAIL.

   Game.finale_scene() stays exactly as it is for clients that ask for the
   scene directly; it simply stops being the thing that fires at the end of a
   menu sitting.

4. THE CODA
   When the player reaches the last beat — "the_prompt_stays" on a pass,
   "the_prompt_waits" on a failure — call ending.mark_coda_seen(state) and
   save. Not on the freeze frame: the two halves of the ending are separate.

5. THE SEAL
   One capability question and it is finalexam.sealed, on the MENTOR rung, the
   same one finale.py asks. Pass the live encounter; inside a measured run this
   returns finalexam.refuse("MENTOR") — {"error": "sealed"} — and nothing else.
   By the time finish_interview calls this, state["interview"] has been cleared
   and the encounter is None, which is correct: the run is over.

6. WHAT THE CLIENT RENDERS
   PASS   out["ending"]["cutscene"] is a finale scene. Its contract is
          finale.WIRING §8: beats with absolute at_ms, camera/stage/fx from the
          closed vocabularies, the freeze and the guitar hit and the title card
          on one millisecond, and `released` staged apart from `freed`.
   FAIL   out["ending"]["cutscene"] is a rematch scene. Same vocabularies, same
          beat shape, no title card, no guitar hit, three acts. Render
          `rematch` as a way back and NEVER as a game over: there is no
          cooldown, nothing was consumed, the portal is open and the practical
          recomposes.
   BOTH   out["ending"]["two_exams"] is the distinction, in a shape a client
          can show on a menu, so the player is never confused about which thing
          they are about to sit.

7. THE ANTAGONIST'S VOICE IS OVERRIDABLE, IN BOTH SCENES
   The brief is that he antagonises all game, at every boss, and that belongs
   to whichever pass owns story.py. These two modules own only his last
   appearance, and both hand the microphone back:

       ending.resolve(..., king_voice={"record": (...), "names": (...),
                                       "held_some": (...), "held_none": (...)})
       finale.cutscene(..., king_voice={"offer": (...), "breaks": (...)})

   ending.FAILURE_VOICE and finale.KING_VOICE are the defaults and the shapes.
   Supplied lines are formatted with {solved}, {total}, {shapes}, {held},
   {carried} and {villages}, all of which are numbers something else measured.
   Whatever is supplied is held to the same rule by validate_scene(): he names
   and he does not remedy. A King who says "you should" fails the build.

8. TESTS
   ending.self_check()["ok"], and one line in
   tests/test_interview_isolation.py for the seal. The claims checked are
   listed above _REMEDY_WORDS; the interesting one is the first, because it is
   the regression that would quietly ruin the game.
"""


CONTRACT = """
What ending.py needs from files it does not own.

FROM engine.py — two call sites and one state key, all in WIRING above. No new
reward key, no new settlement path, no new vocabulary. The pass branch pays in
captives.py's existing world["boons"]/world["routes"] ledger, which the engine
already re-renders after every rescue.

FROM finalexam.py — NOTHING NEW, and this is load-bearing. It is read, never
written:
  report["exam_id"]            matched against the staged id. This is the whole
                               of how the story climax is told apart from a
                               menu sitting, and it already exists.
  report["verdict"]["code"]    READY is the pass. The arithmetic behind it is
                               finalexam._verdict's and is not re-derived here.
  report["solved"] / ["total"] said back to the player by name.
  report["drills"]             cause/skill/occurrences for the route beat; the
                               remediation half ("do", "where") is STRIPPED
                               before the antagonist is composed and
                               validate_scene() fails the build if it reappears.
  report["next"]["recomposes"] the promise that a rematch is a different exam.
  finalexam.sealed / refuse    the one capability check, on the MENTOR rung.

FROM world.py — portal_status(cleared_bosses) and PORTAL_KEY_REQUIREMENT for
the staging gate, and FINAL_TRIAL for where the room is. world.py already says
in its own comments that the portal gates the story and never the measurement;
this module is that paragraph as code.

FROM captives.py (owned by this pass) — liberate(), release_roll(),
roll_call(), still_held(), total(), INDEX_COLLAPSE.

FROM finale.py (owned by this pass) — cutscene()/view(), the Beat dataclass and
the three closed vocabularies, KING_ID/KING_NAME/_TEACHING_WORDS, and
_schedule(). The rematch scene is built from the same primitives on purpose: a
client that can draw one can draw the other with no new code.

WHAT THIS MODULE WILL NEVER DO
  It never composes, grades, re-grades or appeals a practical. It never chooses
  a problem, never grants mastery, never touches the SRS schedule, and never
  returns a number it was not handed by something that measured one. It never
  blocks, delays, gates or charges for anything — least of all for failing, and
  least of all for sitting the measurement.
"""


if __name__ == "__main__":   # pragma: no cover - a maintenance entry point
    import json
    import sys

    _report = self_check()
    print(json.dumps({k: v for k, v in _report.items() if k != "failures"},
                     indent=1))
    for _line in _report["failures"]:
        print("FAIL:", _line)
    if "--scene" in sys.argv:
        _scene = rematch(exam_report=_fake_report("NOT_READY"), still_held=23,
                         carried=2)
        for _beat in _scene["beats"]:
            print(f"\n[{_beat['at_ms']:>6}ms +{_beat['duration_ms']:<5}] "
                  f"{_beat['act']} / {_beat['id']} / {_beat['camera']['move']}")
            for _line in _beat["lines"]:
                _who = _line["name"] or _line["speaker"]
                print(f"    {_who}: {_line['text']}")
    sys.exit(0 if _report["ok"] else 1)
