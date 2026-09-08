"""Renders the trace index as one self-contained HTML file.

**Deviation from the spec, stated deliberately.** phase-6-trace-pr.md suggests "small
FastAPI + HTMX or Streamlit page", and this is a static generator instead. The reason is
the spec's own justification for the feature -- "a screenshot in the README does more
recruiting work than the code" -- which a committed HTML artifact serves directly, with no
server to run, no `uvicorn`/`fastapi` added to a dependency list already carrying torch as
an optional extra, and no risk that the page only exists while someone is running it. The
data is a completed run's history; nothing about it needs a request loop.

**The "diff viewer" criterion cannot be met from the trace, and that is the trace's fault
by design.** Phase 6a forbids storing "full repo contents" in a trace, so the `patch` events
carry file paths and changed-line counts but never diff text. A viewer would therefore have
to read the working tree, which no longer holds that run's state. What is shown instead is
which files each source touched and how many lines -- and the run_id needed to replay it.
"""

from __future__ import annotations

import html
from pathlib import Path

from pmigrate.trace.index import (
    DEFAULT_INDEX_PATH,
    cost_breakdown,
    failure_class_distribution,
    list_runs,
)

_CSS = """
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:2rem auto;
max-width:1100px;color:#1a1a1a;padding:0 1rem}
h1{margin-bottom:.2rem}h2{margin-top:2.2rem;border-bottom:1px solid #e5e5e5;padding-bottom:.3rem}
table{border-collapse:collapse;width:100%;margin:.6rem 0}
th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #eee}
th{background:#fafafa;font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
code{background:#f4f4f4;padding:.1rem .3rem;border-radius:3px;font-size:.9em}
.bar{background:#4a7ebb;height:12px;display:inline-block;border-radius:2px}
.warn{color:#a33;font-weight:600}
.note{background:#fffbe6;border-left:3px solid #e0c000;padding:.6rem .9rem;margin:1rem 0}
.muted{color:#777}
"""


def _bar(value: float, largest: float, width: int = 220) -> str:
    px = 0 if largest <= 0 else max(2, round(width * value / largest))
    return f'<span class="bar" style="width:{px}px"></span>'


def render_dashboard(*, index_path: Path = DEFAULT_INDEX_PATH) -> str:
    runs = list_runs(index_path=index_path)
    costs = cost_breakdown(index_path=index_path)
    classes = failure_class_distribution(index_path=index_path)

    total_usd = sum(c for _, c in ((r.run_id, r.usd) for r in runs))
    unpriced_total = sum(r.unpriced_calls for r in runs)

    out = [
        "<!doctype html><meta charset='utf-8'><title>pmigrate runs</title>",
        f"<style>{_CSS}</style>",
        "<h1>pmigrate — run dashboard</h1>",
        "<p class='muted'>Generated from the audit traces (docs/decisions.md D90/D95). "
        "Every figure here is reconstructed from a run's own JSONL trace, not from the "
        "result store.</p>",
    ]

    if not runs:
        out.append(
            "<p>No traced runs yet. Run <code>pmigrate eval run</code>, then "
            "<code>pmigrate dashboard</code>.</p>"
        )
        return "\n".join(out)

    out.append(
        f"<p><strong>{len(runs)}</strong> runs &middot; "
        f"<strong>${total_usd:.4f}</strong> total recorded spend"
        + (
            f" &middot; <span class='warn'>{unpriced_total} model call(s) carried no price, "
            "so the total is a lower bound</span>"
            if unpriced_total
            else ""
        )
        + "</p>"
    )

    out += [
        "<h2>Runs</h2>",
        "<table><tr><th>run</th><th>events</th><th>llm</th>"
        "<th>tests</th><th>iters</th><th>patches</th><th>errors</th><th>usd</th></tr>",
    ]
    for r in runs:
        tests = (
            f"{r.last_passed}/{r.last_total}"
            if r.last_total
            else "<span class='muted'>none collected</span>"
        )
        err = f"<span class='warn'>{r.errors}</span>" if r.errors else "0"
        out.append(
            f"<tr><td><code>{html.escape(r.run_id)}</code></td>"
            f"<td class='num'>{r.n_events}</td><td class='num'>{r.llm_calls}</td>"
            f"<td class='num'>{tests}</td><td class='num'>{r.iterations}</td>"
            f"<td class='num'>{r.patches_applied}</td><td class='num'>{err}</td>"
            f"<td class='num'>${r.usd:.4f}</td></tr>"
        )
    out.append("</table>")
    out.append(
        "<p class='muted'>“none collected” means the suite produced no test outcomes at "
        "all — usually a collection error — which is different from zero passing.</p>"
    )

    out += ["<h2>Cost</h2>", "<table><tr><th>run</th><th>usd</th><th></th></tr>"]
    largest = max((c for _, c, _ in costs), default=0.0)
    for run_id, usd, unpriced in costs[:15]:
        flag = " <span class='warn'>(lower bound)</span>" if unpriced else ""
        out.append(
            f"<tr><td><code>{html.escape(run_id)}</code></td>"
            f"<td class='num'>${usd:.4f}{flag}</td><td>{_bar(usd, largest)}</td></tr>"
        )
    out.append("</table>")

    out += ["<h2>Failure classes</h2>", "<table><tr><th>class</th><th>n</th><th></th></tr>"]
    biggest = max((n for _, n in classes), default=0)
    for cls, n in classes:
        out.append(
            f"<tr><td><code>{html.escape(cls)}</code></td><td class='num'>{n}</td>"
            f"<td>{_bar(n, biggest)}</td></tr>"
        )
    out.append("</table>")

    out.append(
        "<div class='note'><strong>No diff viewer.</strong> Phase 6a forbids storing full "
        "repo contents in a trace, so <code>patch</code> events carry file paths and "
        "changed-line counts but never diff text. Rendering diffs here would mean reading a "
        "working tree that no longer holds that run's state. Replay a run instead: "
        "<code>pmigrate replay &lt;run_id&gt;</code>.</div>"
    )
    return "\n".join(out)


def write_dashboard(out_path: Path, *, index_path: Path = DEFAULT_INDEX_PATH) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_dashboard(index_path=index_path))
    return out_path
