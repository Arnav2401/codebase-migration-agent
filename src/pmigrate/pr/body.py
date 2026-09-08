"""Generates a draft PR body from a run's trace (docs/phase-6-trace-pr.md).

Everything here is read from `TraceEvent`s, never from the live repo or the result store.
That is the point: phase-6-trace-pr.md asks for a body covering what changed, why, test
results before -> after, failure classes, confidence, cost and iteration count -- and if all
of that can be reconstructed from the trace alone, the trace is doing the job I6 claims for
it. A field this cannot fill is a gap in the trace, which is worth discovering here rather
than believing the trace is complete because nothing ever asked it for anything.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from pmigrate.agent.confidence import ConfidenceScore
from pmigrate.trace.events import TraceEvent

# Below this, the PR is labelled for human review rather than presented as ready. Set where
# it is because D92/D93 measured this score as OVER-CONFIDENT -- the top bucket predicts
# 0.94 and delivers 0.46 -- so a threshold that trusted high scores would wave through
# exactly the runs the calibration says to distrust. Until the score calibrates, this is
# deliberately strict.
NEEDS_REVIEW_BELOW = 0.95

NEEDS_REVIEW_LABEL = "needs-human-review"


@dataclass(frozen=True)
class PrPlan:
    """What a PR would say, derived entirely from a trace."""

    run_id: str
    files_by_source: dict[str, list[str]] = field(default_factory=dict)
    rules_fired: list[str] = field(default_factory=list)
    lines_by_source: dict[str, int] = field(default_factory=dict)
    first_tests: tuple[int, int] | None = None
    last_tests: tuple[int, int] | None = None
    failure_classes: Counter[str] = field(default_factory=Counter)
    iterations: int = 0
    usd: float = 0.0
    unpriced_calls: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def all_files(self) -> list[str]:
        return sorted({f for files in self.files_by_source.values() for f in files})


def plan_from_trace(events: list[TraceEvent]) -> PrPlan:
    files_by_source: dict[str, list[str]] = {}
    lines_by_source: dict[str, int] = {}
    rules: set[str] = set()
    classes: Counter[str] = Counter()
    first_tests: tuple[int, int] | None = None
    last_tests: tuple[int, int] | None = None
    iterations = 0
    usd = 0.0
    unpriced = 0
    errors: list[str] = []

    for e in events:
        p = e.payload
        if e.kind == "patch" and p.get("outcome") == "applied":
            src = str(p.get("source", "?"))
            files_by_source.setdefault(src, [])
            for f in p.get("files_changed", []) or []:
                if f not in files_by_source[src]:
                    files_by_source[src].append(f)
            lines_by_source[src] = lines_by_source.get(src, 0) + int(p.get("lines_changed") or 0)
            rules.update(p.get("rules_fired", []) or [])
        elif e.kind == "test_run":
            pair = (int(p.get("passed") or 0), int(p.get("total") or 0))
            if first_tests is None:
                first_tests = pair
            last_tests = pair
            iterations = max(iterations, int(p.get("iteration") or 0))
        elif e.kind == "triage":
            classes.update(p.get("classes", []) or [])
        elif e.kind == "llm_call":
            usd += e.usd or 0.0
            if e.usd is None:
                unpriced += 1
        elif e.kind == "error":
            errors.append(f"{p.get('where', '?')}: {p.get('message', '')}")

    return PrPlan(
        run_id=events[0].run_id if events else "unknown",
        files_by_source=files_by_source,
        rules_fired=sorted(rules),
        lines_by_source=lines_by_source,
        first_tests=first_tests,
        last_tests=last_tests,
        failure_classes=classes,
        iterations=iterations,
        usd=usd,
        unpriced_calls=unpriced,
        errors=errors,
    )


def build_pr_body(plan: PrPlan, confidence: ConfidenceScore, *, repo_id: str) -> str:
    """The body. Written to be read by a maintainer deciding whether to trust it, so the
    limitations lead rather than trail: an automated PR that buries its own uncertainty is
    worse than one that never opened."""
    needs_review = confidence.value < NEEDS_REVIEW_BELOW
    lines: list[str] = [
        f"# Automated pydantic v1 → v2 migration: `{repo_id}`",
        "",
        "> Opened by [pmigrate](https://github.com/Arnav2401/codebase-migration-agent), an "
        "autonomous migration agent. **Draft, and generated from the run's audit trace.** "
        "Every number below is reconstructed from that trace, not asserted.",
        "",
    ]

    if needs_review:
        lines += [
            f"## ⚠️ Needs human review (confidence {confidence.value:.2f})",
            "",
            "This run is labelled for review rather than presented as ready. The confidence "
            "score is **known to be over-confident** on this project's own calibration set "
            "(`docs/results/calibration.md`): the top bucket predicts 0.94 and delivers 0.46. "
            "Treat the score as a ranking, not a probability.",
            "",
        ]

    if plan.first_tests and plan.last_tests:
        (fp, ft), (lp, lt) = plan.first_tests, plan.last_tests
        lines += [
            "## Test results",
            "",
            # NOT labelled "before": the agent's first test run happens AFTER T1's codemods
            # have already been applied, so calling it a baseline would overstate what this
            # PR changed. The true pre-migration baseline lives in the corpus manifest and
            # is not part of the trace, so the honest label is what these numbers actually
            # are -- the first and last measurements inside the run.
            f"- first measured (after T1 codemods): **{fp}/{ft}** passing",
            f"- final: **{lp}/{lt}** passing",
            f"- iterations: {plan.iterations}",
            "",
            "_The collected-test count can change between runs: a fix to an import error "
            "makes previously-uncollectable tests visible, so a rising denominator is "
            "progress rather than an inconsistency._",
            "",
        ]

    lines += ["## What changed", ""]
    if not plan.files_by_source:
        lines.append("_No patch landed in this run._")
        lines.append("")
    for src in sorted(plan.files_by_source):
        label = {"T1": "Deterministic codemods (T1)", "T2": "Model-written repair (T2/T3)"}.get(
            src, f"source {src}"
        )
        n_lines = plan.lines_by_source.get(src, 0)
        lines.append(f"### {label} — {n_lines} changed lines")
        lines.append("")
        lines.extend(f"- `{f}`" for f in plan.files_by_source[src])
        lines.append("")
    if plan.rules_fired:
        lines += ["Codemod rules that fired: " + ", ".join(f"`{r}`" for r in plan.rules_fired), ""]

    if plan.failure_classes:
        lines += ["## Failure classes encountered", ""]
        lines.extend(f"- `{c}` x{n}" for c, n in sorted(plan.failure_classes.items()))
        lines.append("")

    lines += [
        "## Confidence",
        "",
        f"`{confidence.value:.3f}` — {confidence.explain()}",
        "",
    ]
    if confidence.missing:
        lines += [
            f"Components that could not be measured for this run: "
            f"{', '.join(f'`{m}`' for m in confidence.missing)}. Their weight is redistributed "
            "across the rest rather than scored as zero, so the number stays on the same "
            "scale — but it rests on less evidence than a fully-measured run.",
            "",
        ]

    lines += ["## Cost", "", f"- spend: ${plan.usd:.4f}", f"- iterations: {plan.iterations}"]
    if plan.unpriced_calls:
        lines.append(
            f"- ⚠️ {plan.unpriced_calls} model call(s) carried no price, so the spend above "
            "is a **lower bound**"
        )
    lines.append("")

    if plan.errors:
        lines += ["## Errors during the run", ""]
        lines.extend(f"- {e}" for e in plan.errors[:10])
        lines.append("")

    lines += [
        "---",
        "",
        f"Run id: `{plan.run_id}` — replay with `pmigrate replay {plan.run_id}`.",
    ]
    return "\n".join(lines)
