"""Authored boss rematches with a testable change in the exercise contract.

These are teaching encounters, not sealed or unseen transfer evidence. A new
problem id alone is insufficient: each entry names the changed demand. Selection
stops claiming novelty once the finite authored sequence has been exhausted.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from . import world


@dataclass(frozen=True)
class Variant:
    problem_id: str
    what_changed: str
    constraint: str


MANIFEST = {
    "hash_titan": (Variant("rm-anagram-index-pairs", "Count matching index pairs instead of returning anagram groups.",
                           "Repeated spellings at different positions count separately; character multiplicity matters."),),
    "three_sum_hydra": (Variant("rp-three-sum-pair", "The target is now an argument, and the answer is one triple instead of all zero-sum triples.",
                                "Return the first ascending triple found by the stated sorted traversal, or []."),),
    "window_wraith": (Variant("sw-longest-no-repeat-substr", "Return the repeat-free substring itself instead of its length.",
                              "On equal lengths, return the leftmost substring."),),
    "twin_behemoth": (Variant("tp-trap-water", "Measure all trapped rainwater instead of the largest two-wall container.",
                              "Each bar has unit width; interior basins contribute separately."),
                       Variant("sec-risk-pairing", "Pair sorted scores under a supplied budget instead of measuring water.",
                               "Return pairs in formation order; discard the largest score when the current pair is too expensive.")),
    "matrix_golem": (Variant("rp-matrix-rotate-counter", "Rotate counter-clockwise and return a new grid instead of rotating clockwise in place.",
                             "The returned positions must follow the counter-clockwise mapping."),
                      Variant("mx-transpose", "Transpose rows and columns instead of rotating the grid.",
                              "Rectangular inputs change output dimensions; row order is not reversed.")),
    "tree_dragon": (Variant("rm-bst-subtree-report", "Return ordering validity, height and whole-tree balance instead of a single BST verdict.",
                            "Every subtree must be height-balanced; strict ordering rejects duplicate keys."),),
    "path_sum_ent": (Variant("tr-all-path-sums", "Return every matching root-to-leaf path instead of whether any exists.",
                            "Each path contains its values in root-to-leaf order; internal nodes are not endpoints."),
                     Variant("tr-lowest-common", "Find the shared ancestor of two present values instead of a path with a target sum.",
                             "A node can be its own ancestor; return the lowest qualifying node's value.")),
    "graph_necromancer": (Variant("rm-shortest-node-path", "Return an actual shortest route instead of only its hop count.",
                                  "Respect listed neighbor order for ties; cycles, duplicate edges and unreachable destinations are legal."),),
    "rolling_titan": (Variant("rm-streaming-window-max", "Values arrive through individual push calls, with a reset operation and a warm-up period.",
                              "Return None before k values; expire old maxima and discard all window state on reset."),),
    "editor_automaton": (Variant("ds-undo-redo", "Track action objects with do/undo/redo instead of editing document snapshots.",
                                 "A new action clears redo history; each operation has its own return contract."),),
    "complexity_wyrm": (Variant("rm-wildcard-window-cover", "The target can include wildcard slots as well as repeated literal symbols.",
                                "Each wildcard consumes another position; return the leftmost shortest valid cover."),),
    "serialization_lich": (Variant("rp-tree-deserialize", "Decode preorder tokens into a tree instead of round-tripping a tree representation.",
                                   "'#' records a missing child; consume shared token position correctly across both subtrees."),),
    "bug_demon": (Variant("db-window-slice", "Repair omission of the final fixed-size window instead of duplicate BFS discovery.",
                          "Include every complete window, including the one ending at the last input element."),
                  Variant("db-column-bounds", "Repair a column sum over ragged rows instead of a window boundary.",
                          "Short rows must be handled without indexing beyond their length.")),
    "the_interviewer": (Variant("ds-time-map", "Retrieve the latest value at or before a timestamp instead of evicting by recency.",
                                "Timestamps arrive increasing per key; absent or too-early lookups return ''."),
                        Variant("ds-text-editor", "Implement document edits and undo/redo instead of timestamp lookup.",
                                "Document snapshots and history operations must follow the editor's method contract.")),
}


def _eligible(problem, base) -> bool:
    return bool(problem is not None and base is not None and not getattr(problem, "sealed", False)
                and problem.spaced_repetition_family == base.spaced_repetition_family
                and problem.entry.get("kind") in {"function", "class_ops"}
                and problem.encounter_kind in {"CODE_BATTLE", "DEBUG_BATTLE", "BOSS", "ELITE"}
                and problem.visible_tests and problem.hidden_tests
                and problem.canonical_solution and problem.id != base.id)


def validate_manifest(by_id: Mapping, bosses=None) -> list[str]:
    """Static eligibility; tests independently execute every selected canonical."""
    bosses = world.BOSSES if bosses is None else bosses
    issues = []
    for boss in bosses:
        base = by_id.get(boss["problem_id"])
        entries = MANIFEST.get(boss["id"], ())
        if not entries:
            issues.append(f"{boss['id']}: no authored changed-contract practice")
        seen = set()
        for entry in entries:
            if entry.problem_id in seen:
                issues.append(f"{boss['id']}: repeated variant {entry.problem_id}")
            seen.add(entry.problem_id)
            if not _eligible(by_id.get(entry.problem_id), base):
                issues.append(f"{boss['id']}: missing, sealed, untested or wrong-family variant {entry.problem_id}")
            if not entry.what_changed or not entry.constraint:
                issues.append(f"{boss['id']}: variant has no stated contract change")
    return issues


def get_rematch(boss, rematch: int, by_id: Mapping) -> dict:
    """Return selection metadata; the engine remains owner of phases and rewards.

    `rematch` is completed victories (0 = original fight). Invalid or removed
    variants degrade to an honestly labelled repeat, never unrelated content.
    """
    boss = world.BOSS_BY_ID.get(boss, {}) if isinstance(boss, str) else (boss or {})
    base_id = boss.get("problem_id", "")
    base = by_id.get(base_id)
    entries = MANIFEST.get(boss.get("id", ""), ())
    try:
        number = max(0, int(rematch))
    except (ValueError, TypeError):
        number = 0
    result = {"boss_id": boss.get("id", ""), "base_problem_id": base_id, "problem_id": base_id,
              "rematch": number, "constraint_changed": False, "transfer_evidence": False,
              "kind": "original" if not number else "repeat_practice",
              "what_changed": "Original boss contract." if not number else "No eligible changed contract is available; this is repeat practice.",
              "constraint": "", "exhausted": False}
    if not number or not entries:
        return result
    # Do not silently renumber the sequence when an entry is removed or sealed.
    entry = entries[min(number - 1, len(entries) - 1)]
    if not _eligible(by_id.get(entry.problem_id), base):
        return result
    changed = number <= len(entries)
    result.update(problem_id=entry.problem_id, constraint=entry.constraint,
                  kind="constraint_practice" if changed else "repeat_practice",
                  constraint_changed=changed, exhausted=not changed,
                  what_changed=entry.what_changed if changed else
                  "The authored contract variants are exhausted. Repeat this contract to practise retrieval; it is not fresh transfer evidence.")
    return result
