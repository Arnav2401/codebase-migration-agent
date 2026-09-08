"""Phase 6's calibration report: bucket runs by predicted confidence, show the ACTUAL pass
rate in each bucket (docs/phase-6-trace-pr.md).

The point is not that confidence is high. It is that confidence MEANS something: runs
predicted at 0.8 should pass more of their tests than runs predicted at 0.3. A score that
does not separate the buckets is a number with no content, and this report is what makes
that visible instead of assertable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pmigrate.agent.confidence import ConfidenceInputs, score
from pmigrate.eval.metrics import RepoResult
from pmigrate.trace import load_events
from pmigrate.types import FailureClass


@dataclass(frozen=True)
class Bucket:
    low: float
    high: float
    n: int
    mean_predicted: float
    mean_actual: float

    @property
    def gap(self) -> float:
        """Predicted minus actual. Positive means over-confident, which is the direction
        that matters for a tool that opens PRs."""
        return self.mean_predicted - self.mean_actual


def mechanical_split(trace_path: str | None) -> tuple[int | None, int | None]:
    """Changed lines written by T1 codemods vs by the model, read from the run's own trace
    (docs/decisions.md D93).

    The counts live on `patch` events rather than on `RepoResult` deliberately: it keeps the
    trace load-bearing instead of decorative, which is what I6 claims for it -- if a number
    in a report can only be produced from the trace, the trace demonstrably contains the run.

    Returns `(None, None)` when there is no trace or it carries no patch events with counts,
    so the component stays UNMEASURED rather than being reported as a confident 0%.
    """
    if not trace_path:
        return (None, None)
    path = Path(trace_path)
    if not path.exists():
        return (None, None)
    mechanical = model = 0
    seen = False
    for event in load_events(path.stem, trace_root=path.parent):
        if event.kind != "patch" or "lines_changed" not in event.payload:
            continue
        seen = True
        n = int(event.payload.get("lines_changed") or 0)
        if event.payload.get("source") == "T1":
            mechanical += n
        else:
            model += n
    return (mechanical, model) if seen else (None, None)


def inputs_for(result: RepoResult, *, max_iterations: int = 20) -> ConfidenceInputs:
    """Derives the score's inputs from a scored result, reading the diff composition back
    out of its trace (D93)."""
    counts: Counter[FailureClass] = Counter(result.final_diagnosis_counts)

    # "Few iterations" is ambiguous, and the first calibration run showed it dominating the
    # score in the wrong direction (docs/decisions.md D92): a run can end at iteration 1
    # because it fixed everything immediately, or because repair never engaged at all --
    # no findable target, or every model call rate-limited. `SupImDos__pydantic-argparse`
    # scored 0.933 predicted against 0.000 actual for exactly that reason.
    #
    # So the iterations axis is only informative when the loop actually did something: the
    # run went green, or it made at least one repair attempt. Otherwise it is unmeasured
    # and its weight is redistributed, rather than being read as a confident "converged
    # fast". Not a weight tweak -- the component genuinely has no content in that case.
    mechanical_lines, model_lines = mechanical_split(result.trace_path)
    engaged = result.full_green or bool(result.scored_repairs)
    return ConfidenceInputs(
        mechanical_lines=mechanical_lines,
        model_lines=model_lines,
        iterations=result.iterations if engaged else 0,
        max_iterations=max_iterations if engaged else 0,
        diagnosis_counts=counts,
    )


def calibrate(results: list[RepoResult], *, n_buckets: int = 4) -> list[Bucket]:
    """Equal-width buckets over [0, 1]. Equal-width rather than equal-frequency because a
    calibration plot is read against the diagonal, and equal-frequency buckets would move
    the x-positions around as the data changes, making two runs' plots incomparable."""
    if not results:
        return []
    width = 1.0 / n_buckets
    scored = [(score(inputs_for(r)).value, r.pass_rate) for r in results]
    buckets: list[Bucket] = []
    for i in range(n_buckets):
        low, high = i * width, (i + 1) * width
        members = [
            (p, a) for p, a in scored if (low <= p < high or (i == n_buckets - 1 and p == 1.0))
        ]
        if not members:
            continue
        buckets.append(
            Bucket(
                low=low,
                high=high,
                n=len(members),
                mean_predicted=sum(p for p, _ in members) / len(members),
                mean_actual=sum(a for _, a in members) / len(members),
            )
        )
    return buckets


def render_calibration(buckets: list[Bucket], *, width: int = 40) -> str:
    """An ASCII calibration plot. Deliberately text: it belongs in the repo and a README
    next to the numbers it describes, and a PNG in a docs directory rots separately from
    the data that produced it."""
    if not buckets:
        return "No results to calibrate."
    lines = [
        "Confidence calibration (predicted vs actual pass rate)",
        "",
        f"{'bucket':>12}  {'n':>3}  {'predicted':>9}  {'actual':>7}  {'gap':>6}  plot",
    ]
    for b in buckets:
        pred_col = round(b.mean_predicted * width)
        act_col = round(b.mean_actual * width)
        row = [" "] * (width + 1)
        row[act_col] = "A"
        row[pred_col] = "P" if pred_col != act_col else "*"
        lines.append(
            f"{b.low:.2f}-{b.high:.2f}  {b.n:3d}  {b.mean_predicted:9.3f}  "
            f"{b.mean_actual:7.3f}  {b.gap:+6.3f}  |{''.join(row)}|"
        )
    lines.append("")
    lines.append("P = mean predicted confidence, A = mean actual pass rate, * = they coincide.")
    lines.append("Positive gap = OVER-confident, the direction that matters for opening PRs.")
    return "\n".join(lines)


def write_calibration_report(results: list[RepoResult], out_path: Path) -> None:
    buckets = calibrate(results)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = ["# Confidence calibration", "", render_calibration(buckets), ""]
    if results:
        missing = score(inputs_for(results[0])).missing
        if missing:
            body.append(
                f"Components unmeasured in this run and redistributed: {', '.join(missing)}. "
                "See docs/decisions.md D92 -- an unmeasured component is not scored as zero, "
                "because that would shift every prediction by a constant and make the plot "
                "look well-behaved while being uniformly wrong."
            )
    out_path.write_text("\n".join(body) + "\n")
