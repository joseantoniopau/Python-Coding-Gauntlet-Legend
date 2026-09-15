"""Declarative builders shared by every problem family.

The point of this module is that a full, validated, hint-tree-carrying problem
should cost about twenty lines to author, so the corpus can be broad without
being shallow.
"""
from __future__ import annotations

import textwrap

from ..schema import (Problem, TARGET_SECONDS, build_hint_tree, case, derive,
                      derive_ops, encode_value, ops_case)

__all__ = ["code_problem", "design_problem", "debug_problem", "mcq_problem",
           "forge_problem", "case", "derive", "ops_case", "derive_ops",
           "starter_for", "dedent"]


# Spec section 49: never claim a question was actually asked. Every problem that
# cites reported provenance carries this, appended structurally rather than left
# to whoever authored the entry.
PROVENANCE_DISCLAIMER = (
    " Reported coding exercise patterns, not a guarantee of assessment content."
)


# A provenance note is a claim about where a problem comes from, and every such
# claim has to be disclaimed — not only the ones that name a company. The three
# source types below identify reported coding exercise patterns;
# GENERATED_VARIANT and SECURITY_VARIANT carry their own, stronger note ("never
# presented as a question any company has asked") and must not have this one
# appended on top of it.
CLAIMS_REPORTING = ("REPORTED_INTERVIEW", "COMPANY_PATTERN", "GENERAL_INTERVIEW")


def with_disclaimer(source_type: str, note: str) -> str:
    note = (note or "").strip()
    if source_type not in CLAIMS_REPORTING or not note:
        return note
    if "not a guarantee" in note.lower() or "not a guaranteed" in note.lower():
        return note
    return (note + PROVENANCE_DISCLAIMER).strip()


def dedent(text: str) -> str:
    return textwrap.dedent(text).strip("\n") + "\n"


def starter_for(fn_name: str, params: str, hint_line: str = "") -> str:
    body = f"def {fn_name}({params}):\n"
    if hint_line:
        body += f"    # {hint_line}\n"
    body += "    pass\n"
    return body


def _fragment_of(canonical: str, lines: int = 4) -> str:
    body = [ln for ln in canonical.splitlines() if ln.strip()]
    head = "\n".join(body[:lines])
    return "```python\n" + head + "\n    ...\n```"


def _solution_block(canonical: str) -> str:
    return "```python\n" + canonical.rstrip() + "\n```"


def _mk_tests(reference, spec, *, cmp, hidden, kind, reveal=True):
    out = []
    for entry in spec:
        name, args = entry[0], entry[1]
        this_cmp = entry[2] if len(entry) > 2 else cmp
        out.append(derive(reference, name, list(args), cmp=this_cmp,
                          hidden=hidden, kind=kind, reveal=reveal))
    return out


def code_problem(
    *, id: str, title: str, realm: str, pattern: str, difficulty: str,
    statement: str, fn_name: str, params: str, reference, canonical: str,
    visible: list, hidden: list, edges: list = (), perf: list = (),
    cmp: str = "exact", time_complexity: str = "O(n)", space_complexity: str = "O(n)",
    complexity_choices: list[str] = (), secondary: list[str] = (),
    constraints: list[str] = (), failures: list[str] = (),
    nudge: str = "", visual: str = "", pseudocode: str = "", fragment: str = "",
    viz: dict = None, family: str = "", security: bool = False,
    source_type: str = "GENERAL_INTERVIEW", company: str = "", year: str = "",
    provenance: str = "", encounter: str = "CODE_BATTLE", boss: bool = False,
    prerequisites: list[str] = (), profile_weight: dict = None,
    starter_hint: str = "", starter_code: str = "",
    tags: list[str] = (), examples: list[dict] = None,
    alternates: list[dict] = (), variants: list[str] = (),
    preamble: str = "", arg_adapters: list = (), result_adapter: str = "",
) -> Problem:
    canonical = dedent(canonical)
    vis = _mk_tests(reference, visible, cmp=cmp, hidden=False, kind="correctness")
    hid = _mk_tests(reference, hidden, cmp=cmp, hidden=True, kind="correctness")
    edg = _mk_tests(reference, edges, cmp=cmp, hidden=True, kind="edge", reveal=False)
    prf = []
    for entry in perf:
        name, args = entry[0], entry[1]
        prf.append(derive(reference, name, list(args), cmp=cmp, hidden=True,
                          kind="performance", reveal=False, timeout_ms=2500))

    if examples is None:
        examples = [
            {"input": ", ".join(repr(a) for a in t["args"]), "output": repr(t["expected"])}
            for t in vis[:2]
        ]

    return Problem(
        id=id, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "function", "name": fn_name,
               "signature": f"{fn_name}({params})",
               "preamble": dedent(preamble) if preamble else "",
               "arg_adapters": list(arg_adapters),
               "result_adapter": result_adapter},
        canonical_solution=canonical,
        encounter_kind=encounter,
        secondary_patterns=list(secondary),
        source_type=("SECURITY_VARIANT" if security else source_type),
        reported_company=company, reported_year=year,
        provenance_note=with_disclaimer(source_type, provenance),
        examples=examples, constraints=list(constraints),
        # A scaffolded tier hands the player working code with holes in it, so
        # the generated `def ...: pass` stub has to be overridable.
        starter_code=dedent(starter_code) if starter_code else starter_for(
            fn_name, params, starter_hint),
        visible_tests=vis, hidden_tests=hid, edge_cases=edg, perf_tests=prf,
        alternate_solutions=list(alternates),
        optimal_complexity={"time": time_complexity, "space": space_complexity},
        complexity_choices=list(complexity_choices) or _default_choices(time_complexity),
        common_failures=list(failures),
        hint_tree=build_hint_tree(
            pattern, nudge=nudge, visual=visual,
            pseudocode="```\n" + dedent(pseudocode).strip() + "\n```" if pseudocode else "",
            fragment=fragment or _fragment_of(canonical),
            solution=_solution_block(canonical),
        ),
        visualization=viz or {},
        variants=list(variants),
        security_variant=security,
        spaced_repetition_family=family or pattern.lower(),
        prerequisites=list(prerequisites),
        estimated_seconds=TARGET_SECONDS[difficulty],
        target_seconds=TARGET_SECONDS[difficulty],
        boss_eligible=boss,
        profile_weight=profile_weight or {},
        tags=list(tags),
    )


def design_problem(
    *, id: str, title: str, realm: str, difficulty: str, statement: str,
    cls_name: str, reference_cls, canonical: str, visible: list, hidden: list,
    edges: list = (), constraints: list[str] = (), failures: list[str] = (),
    nudge: str = "", visual: str = "", pseudocode: str = "",
    time_complexity: str = "O(1) amortized", space_complexity: str = "O(n)",
    family: str = "design", security: bool = False, company: str = "",
    source_type: str = "GENERAL_INTERVIEW", provenance: str = "",
    boss: bool = False, secondary: list[str] = (), viz: dict = None,
    profile_weight: dict = None, tags: list[str] = (),
) -> Problem:
    canonical = dedent(canonical)

    def build(spec, hidden_flag, kind, reveal=True):
        out = []
        for name, ops, args in spec:
            out.append(derive_ops(reference_cls, name, ops, args,
                                  hidden=hidden_flag, reveal=reveal))
            out[-1]["kind"] = kind
        return out

    vis = build(visible, False, "correctness")
    hid = build(hidden, True, "correctness")
    edg = build(edges, True, "edge", reveal=False)

    return Problem(
        id=id, title=title, realm=realm, pattern="DESIGN", difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "class_ops", "name": cls_name, "signature": f"class {cls_name}"},
        canonical_solution=canonical, encounter_kind="CODE_BATTLE",
        secondary_patterns=list(secondary), source_type=source_type,
        reported_company=company,
        provenance_note=with_disclaimer(source_type, provenance),
        examples=[{"input": " -> ".join(t["ops"]), "output": repr(t["expected"])}
                  for t in vis[:1]],
        constraints=list(constraints),
        starter_code=f"class {cls_name}:\n    def __init__(self):\n        pass\n",
        visible_tests=vis, hidden_tests=hid, edge_cases=edg,
        optimal_complexity={"time": time_complexity, "space": space_complexity},
        complexity_choices=_default_choices(time_complexity),
        common_failures=list(failures),
        hint_tree=build_hint_tree(
            "DESIGN", nudge=nudge, visual=visual,
            pseudocode="```\n" + dedent(pseudocode).strip() + "\n```" if pseudocode else "",
            fragment=_fragment_of(canonical, 6), solution=_solution_block(canonical),
        ),
        visualization=viz or {},
        security_variant=security, spaced_repetition_family=family,
        estimated_seconds=TARGET_SECONDS[difficulty],
        target_seconds=TARGET_SECONDS[difficulty], boss_eligible=boss,
        profile_weight=profile_weight or {}, tags=list(tags),
    )


def debug_problem(
    *, id: str, title: str, difficulty: str, statement: str, fn_name: str,
    params: str, broken: str, reference, canonical: str, visible: list,
    hidden: list, bug_type: str, armor_piece: str, cmp: str = "exact",
    nudge: str = "", failures: list[str] = (), pattern: str = "DEBUGGING",
    realm: str = "debugging_dungeon", family: str = "debugging",
    time_complexity: str = "O(n)", space_complexity: str = "O(n)",
    security: bool = False,
) -> Problem:
    canonical, broken = dedent(canonical), dedent(broken)
    vis = _mk_tests(reference, visible, cmp=cmp, hidden=False, kind="correctness")
    hid = _mk_tests(reference, hidden, cmp=cmp, hidden=True, kind="correctness")
    return Problem(
        id=id, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "function", "name": fn_name, "signature": f"{fn_name}({params})"},
        canonical_solution=canonical, encounter_kind="DEBUG_BATTLE",
        secondary_patterns=["DEBUGGING"],
        source_type="SECURITY_VARIANT" if security else "GENERAL_INTERVIEW",
        examples=[{"input": ", ".join(repr(a) for a in t["args"]),
                   "output": repr(t["expected"])} for t in vis[:2]],
        starter_code=broken,
        visible_tests=vis, hidden_tests=hid,
        optimal_complexity={"time": time_complexity, "space": space_complexity},
        common_failures=list(failures),
        hint_tree=build_hint_tree(
            "DEBUGGING",
            nudge=nudge or "Run it first. Let the failing test tell you the input.",
            visual="Trace the failing input by hand, one line at a time. "
                   "Where does the real state first diverge from what you expected?",
            pseudocode="```\nBug class: " + bug_type + "\n```",
            fragment=_fragment_of(canonical), solution=_solution_block(canonical),
        ),
        spaced_repetition_family=family,
        estimated_seconds=TARGET_SECONDS[difficulty],
        target_seconds=TARGET_SECONDS[difficulty],
        security_variant=security,
        tags=["bug:" + bug_type, "armor:" + armor_piece],
    )


def mcq_problem(
    *, id: str, title: str, realm: str, pattern: str, difficulty: str,
    statement: str, choices: list[str], answer: int, explanation: str,
    encounter: str = "PATTERN_ENCOUNTER", code: str = "",
    family: str = "", security: bool = False, seconds: int = 60,
    distractor_notes: dict = None,
) -> Problem:
    return Problem(
        id=id, title=title, realm=realm, pattern=pattern, difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "mcq", "name": id, "signature": ""},
        canonical_solution=choices[answer],
        encounter_kind=encounter,
        source_type="SECURITY_VARIANT" if security else "GENERAL_INTERVIEW",
        mcq={"choices": choices, "answer": answer, "explanation": dedent(explanation),
             "code": dedent(code) if code else "",
             "distractors": distractor_notes or {}},
        optimal_complexity={},
        hint_tree=[{"level": 1, "spell": "ORACLE", "mana": 2, "rank_cost": "A",
                    "title": "Oracle", "body": "Eliminate the two answers that cannot "
                                               "possibly hold for the largest input."}],
        spaced_repetition_family=family or pattern.lower(),
        estimated_seconds=seconds, target_seconds=seconds,
        security_variant=security,
    )


def forge_problem(
    *, id: str, title: str, realm: str, difficulty: str, statement: str,
    fn_name: str, correct: str, mutants: list[str], kills: list,
    nudge: str = "", family: str = "testing", min_kills: int = None,
) -> Problem:
    """TEST FORGE: the player writes tests. Their suite must accept the correct
    implementation and reject every mutant. A Mimic that survives is a bug that
    ships.

    `kills` is one argument list per mutant: an input on which that mutant
    genuinely disagrees with the correct implementation. It is required, and
    `validate` runs it, because a mutant that behaves identically to the honest
    implementation cannot be killed by any suite — and since `min_kills` defaults
    to every mutant, one such Mimic makes the whole encounter unwinnable. That is
    exactly the "fight with no win condition" the puzzle validators already
    refuse; this is the same refusal for the Forge.

    The inputs never reach the client: `schema.PUZZLE_VISIBLE_MCQ` lists
    `min_kills` alone as the visible field.
    """
    mutants = [dedent(m) for m in mutants]
    return Problem(
        id=id, title=title, realm=realm, pattern="TESTING", difficulty=difficulty,
        problem_statement=dedent(statement),
        entry={"kind": "test_forge", "name": fn_name, "signature": f"{fn_name}(...)"},
        canonical_solution=dedent(correct), encounter_kind="TEST_FORGE",
        starter_code=dedent(f"""
            # Return a list of (args, expected) pairs.
            # args must be a tuple. Every pair must hold for a CORRECT {fn_name}.
            def tests():
                return [
                    (([1, 2, 3],), 6),
                ]
        """),
        mutants=mutants,
        common_failures=["Only testing the happy path",
                         "No empty input", "No duplicates", "No single element"],
        hint_tree=build_hint_tree(
            "TESTING",
            nudge=nudge or "A weak suite is one every wrong implementation still passes.",
            visual="For each mutant, ask: what input would make this lie show?",
            pseudocode="```\nnormal / empty / one item / duplicates / negatives /\n"
                       "already sorted / reversed / all identical / large\n```",
            fragment="```python\n(([],), 0),\n(([5],), 5),\n(([-1, -2],), -3),\n```",
            solution="```python\n# A suite that kills every mutant must probe the "
                     "boundaries,\n# not just the middle of the input space.\n```",
        ),
        spaced_repetition_family=family,
        estimated_seconds=420, target_seconds=420,
        mcq={"min_kills": min_kills if min_kills is not None else len(mutants),
             "kill_inputs": [encode_value(list(args)) for args in kills]},
    )


_LADDER = ["O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)", "O(n!)"]


def _default_choices(answer: str) -> list[str]:
    if answer not in _LADDER:
        return [answer, "O(n)", "O(n log n)", "O(n^2)"]
    i = _LADDER.index(answer)
    picks = {answer}
    for offset in (-1, 1, 2, -2, 3):
        j = i + offset
        if 0 <= j < len(_LADDER):
            picks.add(_LADDER[j])
        if len(picks) == 4:
            break
    return sorted(picks, key=_LADDER.index)
