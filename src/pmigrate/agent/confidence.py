"""Phase 6's confidence score (docs/phase-6-trace-pr.md).

The spec is explicit that this must be defined rather than hand-waved:

    confidence = w1 * (fraction of changed lines from `mechanical` codemods)
               + w2 * (1 - normalized iterations-to-green)
               + w3 * (1 - fraction of diagnoses in the hard classes)
               + w4 * (test coverage of the changed symbols, if measurable)

Each component answers "why would I distrust this migration?" with something this project
actually measures. T1's codemods are deterministic and rule-bound, so a diff that is mostly
T1 is more trustworthy than one the model wrote freehand (a claim D85 sharpened: the model
was confidently producing patches that renamed a symbol pydantic had deleted). A run that
needed many iterations was one the agent kept getting wrong. And the hard failure classes
are the ones where a plausible-looking patch is most likely to be semantically wrong.

`w4` is REPORTED AS UNMEASURED, not silently zero -- see `ConfidenceScore.missing` and
`docs/decisions.md D92`. This project has no per-symbol coverage data, and the spec's own
"if measurable" is doing real work there.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from pmigrate.types import FailureClass

# Classes where a patch that LOOKS right is most likely to be semantically wrong: these
# turn on runtime behaviour (coercion, serialization shape, message text) rather than on a
# symbol that either exists or does not. An import error is mechanically checkable -- the
# import resolves or it does not -- which is why it is not here.
HARD_CLASSES: frozenset[FailureClass] = frozenset(
    {
        FailureClass.VALIDATION_BEHAVIOUR,
        FailureClass.SERIALIZATION_DIFF,
        FailureClass.ERROR_MESSAGE_DIFF,
        FailureClass.UNKNOWN,
    }
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "mechanical": 0.40,
    "iterations": 0.20,
    "easy_classes": 0.25,
    "symbol_coverage": 0.15,
}


@dataclass(frozen=True)
class ConfidenceInputs:
    """Everything the score needs, each `None` when genuinely unmeasurable rather than
    defaulted -- the distinction D71 already had to make for diff-similarity."""

    mechanical_lines: int | None = None
    model_lines: int | None = None
    iterations: int = 0
    max_iterations: int = 20
    diagnosis_counts: Counter[FailureClass] = field(default_factory=Counter)
    symbol_test_coverage: float | None = None


@dataclass(frozen=True)
class ConfidenceScore:
    value: float
    components: dict[str, float]
    weights_used: dict[str, float]
    missing: tuple[str, ...]

    def explain(self) -> str:
        parts = [
            f"{name}={self.components[name]:.3f}*{self.weights_used[name]:.2f}"
            for name in sorted(self.components)
        ]
        line = f"confidence={self.value:.3f}  ({' + '.join(parts)})"
        if self.missing:
            line += f"  [unmeasured, weight redistributed: {', '.join(self.missing)}]"
        return line


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def score(inputs: ConfidenceInputs, weights: dict[str, float] | None = None) -> ConfidenceScore:
    """Weighted sum over whichever components are measurable, with the unmeasurable ones'
    weight REDISTRIBUTED across the rest rather than contributed as zero.

    Treating an unmeasured component as 0.0 would systematically depress every score by a
    fixed amount, which is not "less confident" -- it is a different, wrong scale, and it
    would make the calibration plot look well-behaved while being uniformly shifted. Same
    principle as D71: not measured is not a real zero.
    """
    w = dict(weights or DEFAULT_WEIGHTS)
    components: dict[str, float] = {}
    missing: list[str] = []

    total_lines = (inputs.mechanical_lines or 0) + (inputs.model_lines or 0)
    if inputs.mechanical_lines is None or total_lines == 0:
        # No diff at all is not "0% mechanical" -- there is nothing to be confident or
        # doubtful about, so the component is absent rather than worst-case.
        missing.append("mechanical")
    else:
        components["mechanical"] = _clamp(inputs.mechanical_lines / total_lines)

    if inputs.max_iterations <= 0:
        missing.append("iterations")
    else:
        components["iterations"] = _clamp(1.0 - inputs.iterations / inputs.max_iterations)

    total_diagnoses = sum(inputs.diagnosis_counts.values())
    if total_diagnoses == 0:
        # A green run diagnoses nothing. That is genuinely no evidence either way about
        # how hard the failures were, so it must not be read as "all classes were easy".
        missing.append("easy_classes")
    else:
        hard = sum(n for cls, n in inputs.diagnosis_counts.items() if cls in HARD_CLASSES)
        components["easy_classes"] = _clamp(1.0 - hard / total_diagnoses)

    if inputs.symbol_test_coverage is None:
        missing.append("symbol_coverage")
    else:
        components["symbol_coverage"] = _clamp(inputs.symbol_test_coverage)

    live = {k: v for k, v in w.items() if k in components}
    live_total = sum(live.values())
    if live_total == 0:
        return ConfidenceScore(0.0, {}, {}, tuple(sorted(missing)))
    normalized = {k: v / live_total for k, v in live.items()}
    value = sum(components[k] * normalized[k] for k in components)
    return ConfidenceScore(_clamp(value), components, normalized, tuple(sorted(missing)))
