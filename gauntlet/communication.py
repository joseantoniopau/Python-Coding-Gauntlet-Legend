"""Problem-specific communication prompts, with honest offline topic coverage.

This does not understand or grade natural-language reasoning. It extracts stated
claims, compares explicit cost notation with authored metadata, and leaves the
semantic check to the learner. It never treats vocabulary as proof of mastery.
"""
from __future__ import annotations

import re

PATTERN_PROMPTS = {
    "LANGUAGE": ("Which Python expression or statement produces the requested value?",
                 "What value or type must the expression produce, and what does each name refer to?",
                 "Trace one legal boundary value and check its value and type."),
    "HASH_MAP": ("What does each key and value represent, and which lookup does the plan need?",
                 "Before each input item, what information does the dictionary contain?",
                 "Check repeated values and an empty input when allowed by the contract."),
    "SET": ("What membership fact does the set record?",
            "When is an item first added, and what is already known about every stored item?",
            "Check duplicates and an empty input when permitted."),
    "SLIDING_WINDOW": ("When does the window expand, and what makes it shrink?",
                       "What condition is true of the current window when an answer is recorded?",
                       "Check a repeated boundary value and a target that cannot be met."),
    "TWO_POINTER": ("What does each pointer mark, and which pointer moves next?",
                    "Why can the portion discarded by each move contain no required answer?",
                    "Check pointer crossing, equal values and the smallest permitted input."),
    "TREE": ("What information passes into a subtree, and what does it return?",
             "What claim is true for each completed subtree?",
             "Check an empty tree, one child and a value that violates an ancestor's rule, when applicable."),
    "BFS": ("What enters the frontier and when is a node marked discovered?",
            "Why does the frontier process the required distance layers in order?",
            "Check a cycle, two routes to one node and an unreachable destination."),
    "DFS": ("What does one traversal call explore and when is a node marked visited?",
            "What is true of the visited set or path when a call returns?",
            "Check a cycle, disconnected nodes and the smallest permitted graph."),
    "QUEUE": ("Which pending candidates belong in the queue, and when do they expire?",
              "Why can each removed candidate no longer affect a future answer?",
              "Check equal candidates, expiration and a window larger than the available input."),
    "STACK": ("What unfinished work does each stack entry represent?",
              "What must hold between the stack's entries after each operation?",
              "Check an empty stack, unmatched items and repeated values when relevant."),
    "BINARY_SEARCH": ("What interval contains the answer, and which half can be discarded?",
                      "State the meaning of both bounds before each iteration.",
                      "Check an absent target, equal values and a one-element interval."),
    "RECURSION": ("What smaller problem does one recursive call solve?",
                  "What is returned by a correct smaller call, and why does recursion terminate?",
                  "Check the base case and the smallest input requiring another call."),
    "DP": ("What does one state mean, and which earlier states does it depend on?",
           "When a state is filled, why are its dependencies already correct?",
           "Check the initial state, an impossible state and competing choices."),
    "MATRIX": ("How do source indices map to destination indices?",
               "Which cells are already correct, and how is unread input preserved?",
               "Check a single cell and rectangular input only if the contract permits it."),
    "DESIGN": ("State the meaning of the object's stored state and each operation's output.",
               "What relationship between the stored structures survives every operation?",
               "Check an empty state, repeated operations and operation order."),
    "DEBUGGING": ("Name the incorrect behavior and the smallest change that addresses its cause.",
                  "What should be true at the failing line before and after the fix?",
                  "Trace a minimal counterexample and a case that should continue to work."),
}
FAMILY_PROMPTS = {
    "anagrams": ("What signature groups exactly the words with the same character counts?",
                 "For each signature, what does the stored group or count represent after each word?",
                 "Check repeated words, repeated letters and empty words if allowed."),
    "bst": ("How will the plan enforce the ordering requirement beyond immediate children?",
            "What ordering information is valid for every completed subtree?",
            "Check duplicate keys and a descendant that violates an ancestor's bound."),
    "tree_paths": ("What path information must be carried into each child?",
                   "At a leaf, what does the remaining target or accumulated path mean?",
                   "Check a node with only one child and a path that ends before a leaf."),
    "tree_serialize": ("How will the representation preserve both values and missing children?",
                       "Where is the reader or writer positioned after one complete subtree?",
                       "Check an empty tree, a single node and a missing left or right child."),
    "rolling_max": ("Which current-window candidates must survive until the next value?",
                    "Why is the next reported maximum still inside the current window?",
                    "Check equal maxima, expiry of the oldest maximum and the warm-up window."),
    "window_cover": ("How are required multiplicities tracked while the window changes?",
                     "What proves that the current window satisfies every required count?",
                     "Check repeated target symbols, an impossible cover and tie behavior."),
}
_DEFAULT = ("Describe how the input becomes the required output.",
            "What must remain true as the computation progresses?",
            "Trace a smallest legal input and a boundary case from the statement.")


def rubric(problem) -> dict:
    pattern = str(getattr(problem, "pattern", ""))
    family = str(getattr(problem, "spaced_repetition_family", ""))
    approach, invariant, edge = FAMILY_PROMPTS.get(family, PATTERN_PROMPTS.get(pattern, _DEFAULT))
    costs = getattr(problem, "optimal_complexity", {}) or {}
    return {
        "problem_id": getattr(problem, "id", ""), "pattern": pattern, "family": family,
        "contract": str(getattr(problem, "problem_statement", "")).strip().split("\n\n")[0][:600],
        "constraints": list(getattr(problem, "constraints", []) or []),
        "expected_time": costs.get("time"), "expected_space": costs.get("space"),
        "prompts": {"approach": approach, "invariant": invariant, "edge_case": edge,
                    "time": "State total time, define the input-size variables, and justify the work.",
                    "space": "State auxiliary space separately, including any recursion stack."},
    }


def _costs(text: str) -> list[tuple[str, int, int]]:
    """Balanced O(...) spans; nested len/min expressions are not cut short."""
    found = []
    for match in re.finditer(r"\bo\s*\(", text, re.I):
        depth, end = 1, match.end()
        while end < len(text) and depth:
            depth += (text[end] == "(") - (text[end] == ")")
            end += 1
        if depth == 0:
            found.append((text[match.start():end], match.start(), end))
    return found


def _normal_cost(text: str) -> str:
    return re.sub(r"[\s*·×]", "", text.lower().replace("**", "^"))


def _cost_claims(text: str, dimension: str) -> list[str]:
    matches = []
    for claim, start, end in _costs(text):
        after = re.match(r"[ \t]*(?:(?:total|auxiliary)[ \t]+)?(time|space|memory)\b", text[end:], re.I)
        before = re.search(r"\b(time|space|memory)(?:\s+(?:complexity|cost|is|of))?\s*[:=]?\s*$", text[max(0, start-45):start], re.I)
        label = (after or before)
        if label and ("space" if label[1].lower() == "memory" else label[1].lower()) == dimension:
            matches.append(claim)
    # Plain-language costs are accepted only when the dimension is explicit.
    aliases = {"constant": "O(1)", "linear": "O(n)", "quadratic": "O(n^2)", "logarithmic": "O(log n)"}
    dim = "(?:space|memory)" if dimension == "space" else "time"
    for word, claim in aliases.items():
        if re.search(rf"\b{word}\s+{dim}\b|\b{dim}\s*(?:is|:)\s*{word}\b", text, re.I):
            matches.append(claim)
    return list(dict.fromkeys(matches))


def _snippet(text: str, key: str) -> str:
    labels = {"approach": r"approach|plan", "invariant": r"invariant|state claim|value claim",
              "edge_case": r"edge case|boundary|counterexample"}
    explicit = re.search(rf"(?:^|\n)\s*(?:{labels[key]})\s*:\s*([^\n]+)", text, re.I)
    if explicit and len(explicit[1].split()) >= 4:
        return explicit[1].strip()[:300]
    anchors = {
        "approach": r"\b(return|compute|convert|compare|traverse|iterate|sort|scan|count|use|build|fix|update)\b",
        "invariant": r"\b(before|after|each|always|maintain|invariant|guarantee|remains?|preserve|returned value|parameter)\b",
        "edge_case": r"\b(empty|zero|negative|duplicate|single|boundary|cycle|unreachable|missing|no match|one child|none)\b",
    }
    for sentence in re.split(r"[.!?\n]+", text):
        if len(sentence.split()) >= 6 and re.search(anchors[key], sentence, re.I):
            return sentence.strip()[:300]
    return ""


def checklist(text: str, problem) -> dict:
    """Backward-compatible score/checks are topic coverage, never correctness."""
    text = str(text or "")[:12000]
    spec = rubric(problem)
    checks = []
    for key, label in (("approach", "Stated an approach"), ("invariant", "Stated a value or invariant claim"),
                       ("edge_case", "Described a boundary check")):
        claim = _snippet(text, key)
        checks.append({"id": key, "label": label, "passed": bool(claim),
                       "status": "stated_unverified" if claim else "missing",
                       "evidence": claim, "why": spec["prompts"][key],
                       "self_check": "Does this claim hold for the exact contract and your code?"})
    for dimension in ("time", "space"):
        expected = spec[f"expected_{dimension}"]
        claims = _cost_claims(text, dimension)
        reference = _costs(str(expected or ""))
        reference_terms = {_normal_cost(c[0]) for c in reference}
        claimed_terms = {_normal_cost(c) for c in claims}
        matches = bool(reference_terms) and claimed_terms == reference_terms
        status = ("matches_reference_not_verified" if matches else "differs_from_reference") if claims and reference_terms else (
            "stated_unverified" if claims else "missing")
        checks.append({"id": dimension, "label": f"Stated {dimension} cost", "passed": matches if reference_terms else bool(claims),
                       "status": status, "evidence": "; ".join(claims), "expected": expected,
                       "why": (f"Authored reference: {expected}. " if expected else "No authored cost is available. ") + spec["prompts"][dimension],
                       "self_check": "Check variable definitions and assumptions; matching notation does not prove this cost."})
    covered = sum(c["passed"] for c in checks)
    score = round(100 * covered / len(checks))
    return {"score": score, "score_kind": "topic_coverage", "checks": checks, "criteria": checks,
            "verdict": f"{covered}/{len(checks)} communication topics covered. Self-check the claims; reasoning correctness is unverified.",
            "semantic_status": "unverified", "self_check_required": True,
            "rubric": spec, "prompts": spec["prompts"],
            "model_answer": ("Answer outline: describe the plan, state what stays true, trace a legal boundary case, "
                             "then justify total time and auxiliary space. "
                             f"Reference costs: {spec['expected_time'] or 'not specified'} time; "
                             f"{spec['expected_space'] or 'not specified'} space. These are prompts, not a verified explanation of your code.")}
