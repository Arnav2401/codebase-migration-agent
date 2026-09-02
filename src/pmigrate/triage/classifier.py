"""The real `Classifier` (triage/protocol.py): rule-based, no LLM. `FailureClass.UNKNOWN`
is the deliberate fallback for anything `rules.py` doesn't recognize — docs/phase-4-triage.md:
"every UNKNOWN you see is a candidate new rule." No LLM classifier is built for the
unmatched case (interfaces.md §6 anticipates one) — the same reasoning `agent/model_client.py`
already gives for why T2 waited for a real key rather than a guessed integration applies
here too: an LLM fallback path can't be verified without exercising it against real
UNKNOWN cases, and none have been collected yet (docs/phase-4-triage.md's own acceptance
criteria call for ≥100 hand-labelled real failures before a classifier's accuracy even
means anything).
"""

from __future__ import annotations

from dataclasses import dataclass

from pmigrate.triage.collect import collect_raw_failures
from pmigrate.triage.grouping import classify_and_group
from pmigrate.types import BaselineResult, Diagnosis, TestRun


@dataclass
class RuleBasedClassifier:
    def classify(self, run: TestRun, baseline: BaselineResult | None) -> list[Diagnosis]:
        return classify_and_group(collect_raw_failures(run), baseline)
