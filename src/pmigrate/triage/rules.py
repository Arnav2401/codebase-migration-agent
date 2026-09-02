"""Rule-first failure classification (docs/phase-4-triage.md). Deliberately narrower than
`FailureClass`'s full taxonomy: only classes with REAL evidence from an actual corpus run
this session get a rule here. `SERIALIZATION_DIFF`, `ERROR_MESSAGE_DIFF`, and `FLAKY` are
NOT implemented — inventing a regex for a failure shape never actually seen would be
guessing, not engineering, exactly what this doc's own "every UNKNOWN is a candidate new
rule" framing argues against. They fall to `FailureClass.UNKNOWN` until a real run
surfaces one.

`FLAKY` specifically needs a different signal than any of these (the SAME node passing on
one run and failing on another) — that's information about two `TestRun`s, not one, so it
doesn't fit a stateless `classify_text(text) -> ...` rule at all. It belongs at the
orchestration layer (agent/graph.py, alongside `NoProgressDetector`, which already tracks
state across iterations), not here.

Each rule maps to a real failure shape already hit and documented in docs/decisions.md:
  - IMPORT_ERROR:       D19/D20 — `PydanticImportError`, `BaseSettings` import failures
  - THIRD_PARTY_PIN:    D26     — `aiomcache` (any non-pydantic `ModuleNotFoundError`)
  - CLASS_DEF_ERROR:    pydantic's own documented error taxonomy (PydanticUserError at
                        class-definition time) — a real, distinct exception type from
                        PydanticImportError, not yet hit in THIS corpus but cheap and
                        unambiguous to detect by exception name alone
  - REMOVED_API:        matches T1's own rule names (`.dict()`/`.json()`/`parse_obj`/
                        `__fields__`) — see the strategy note below for why this is no
                        longer "re-run the codemod"
  - VALIDATION_BEHAVIOUR: D20/D26/D35 — any ValidationError not otherwise classified;
                        the true "needs semantic judgment" class

Rules are tried in order; the first match wins. `PREEXISTING` is NOT one of these regex
rules — it depends on baseline data, not the failure text, and is checked in
`classifier.py` before any of these run at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pmigrate.types import FailureClass

# REMOVED_API's strategy is "flag as a missing/buggy T1 rule," not "re-run T1" — by the
# time triage ever sees a failure, T1 has ALREADY run eagerly, repo-wide, unconditionally
# (docs/decisions.md D18/D19). A REMOVED_API-shaped failure surviving past that means T1's
# rule set doesn't cover this specific call shape yet, which is a more actionable finding
# (a candidate new codemod rule) than routing something mechanical to an LLM.
_STRATEGY_MISSING_T1_RULE = "missing_t1_rule"
_STRATEGY_FIX_IMPORT = "fix_import"
_STRATEGY_PIN_DEPENDENCY = "pin_dependency"
_STRATEGY_FIX_CLASS_DEF = "fix_class_def"
_STRATEGY_SEMANTIC_REPAIR = "semantic_repair"


@dataclass(frozen=True)
class ClassificationRule:
    cls: FailureClass
    strategy: str
    pattern: re.Pattern[str]
    confidence: float = 0.9  # rule-based classification is high-confidence by construction


_MODULE_NOT_FOUND = re.compile(r"ModuleNotFoundError: No module named '(\w+)'")
_PYDANTIC_FAMILY_MODULES = {"pydantic", "pydantic_core", "pydantic_settings"}


def _third_party_pin_match(text: str) -> re.Match[str] | None:
    match = _MODULE_NOT_FOUND.search(text)
    if match is None or match.group(1) in _PYDANTIC_FAMILY_MODULES:
        # a missing pydantic-family module is a T1/sandbox coverage gap (extra_packages()
        # in sandbox/image.py should already prevent this) — NOT a third-party pin;
        # letting it fall through here means it correctly reaches UNKNOWN instead of
        # being mis-filed as "someone else's dependency problem."
        return None
    return match


_RULES: tuple[ClassificationRule, ...] = (
    ClassificationRule(
        cls=FailureClass.IMPORT_ERROR,
        strategy=_STRATEGY_FIX_IMPORT,
        pattern=re.compile(
            r"PydanticImportError|ImportError: cannot import name '\w+' from 'pydantic'"
        ),
    ),
    ClassificationRule(
        cls=FailureClass.CLASS_DEF_ERROR,
        strategy=_STRATEGY_FIX_CLASS_DEF,
        pattern=re.compile(r"pydantic\.errors\.PydanticUserError"),
    ),
    ClassificationRule(
        cls=FailureClass.REMOVED_API,
        strategy=_STRATEGY_MISSING_T1_RULE,
        pattern=re.compile(
            r"has no attribute '(dict|json|parse_obj|parse_raw|__fields__|update_forward_refs)'"
        ),
    ),
    ClassificationRule(
        cls=FailureClass.VALIDATION_BEHAVIOUR,
        strategy=_STRATEGY_SEMANTIC_REPAIR,
        pattern=re.compile(r"pydantic_core\._pydantic_core\.ValidationError"),
    ),
)


def classify_text(text: str) -> ClassificationRule | None:
    """Returns the first matching rule, or None (caller falls back to UNKNOWN).
    `THIRD_PARTY_PIN` is checked separately (via `_third_party_pin_match`) because its
    match needs a captured-group exclusion the plain `ClassificationRule.pattern` shape
    doesn't support — kept as a special case rather than complicating every rule's shape
    for the sake of one."""
    if _third_party_pin_match(text) is not None:
        return ClassificationRule(
            cls=FailureClass.THIRD_PARTY_PIN,
            strategy=_STRATEGY_PIN_DEPENDENCY,
            pattern=_MODULE_NOT_FOUND,
        )
    for rule in _RULES:
        if rule.pattern.search(text):
            return rule
    return None
