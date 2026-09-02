"""Runs a sequence of CodemodRules over one file's source (docs/phase-3-loop.md T1: T1
codemods run first, unconditionally, before any LLM involvement). Rules are applied in
order, each seeing the output of the previous one — order matters for rules whose output
another rule's `applies()` might match (none currently do, but the engine doesn't assume
otherwise).

A single rule's `apply()` call is isolated with a broad except (docs/decisions.md D22):
rules are heuristic pattern-matches on source SHAPE, not verified against semantics
(protocol.py's own docstring), so a rule can hit a shape its author didn't anticipate on
arbitrary real-world code — this is a genuine system boundary (untrusted third-party
source), not internal state we control. Found live: `validator_to_field_validator`
asserted a decorator was always a Call and crashed on a real repo's unrelated, same-named
decorator. Before that fix, one rule's wrong assumption on one file aborted the ENTIRE
remaining run (`edit_t1` processes every file in one call) — the same failure mode as not
isolating a rejected `apply_patch` result, just one level up. This is deliberately
generic (not per-rule fixes for shapes as they're discovered) because the failure mode
itself — any heuristic rule, any unanticipated shape — is generic.
"""

from __future__ import annotations

from dataclasses import replace

import libcst as cst
import structlog

from pmigrate.codemod.protocol import CodemodRule, RuleEdit

log = structlog.get_logger()


def apply_rules(source: str, path: str, rules: list[CodemodRule]) -> tuple[str, list[RuleEdit]]:
    tree = cst.parse_module(source)
    all_edits: list[RuleEdit] = []

    for rule in rules:
        if not rule.applies(tree):
            continue
        try:
            tree, edits = rule.apply(tree)
        except Exception as exc:  # broad on purpose — see module docstring
            log.warning("codemod.rule_failed", rule_id=rule.id, path=path, error=str(exc))
            continue
        all_edits.extend(replace(e, path=path) for e in edits)

    return tree.code, all_edits
