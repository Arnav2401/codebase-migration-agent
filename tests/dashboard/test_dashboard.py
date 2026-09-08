from pathlib import Path

from pmigrate.dashboard import render_dashboard, write_dashboard
from pmigrate.trace import TraceWriter
from pmigrate.trace.index import cost_breakdown, failure_class_distribution, list_runs, rebuild


def _traces(root: Path) -> None:
    a = TraceWriter("repo_a__graph__seed0", trace_root=root)
    a.emit("test_run", {"passed": 1, "total": 10, "iteration": 1})
    a.emit("triage", {"classes": ["import_error", "unknown"]})
    a.emit("llm_call", {"model": "m"}, tokens_in=10, tokens_out=2, usd=0.05)
    a.emit(
        "patch",
        {"source": "T2", "outcome": "applied", "files_changed": ["x.py"], "lines_changed": 4},
    )
    a.emit("test_run", {"passed": 9, "total": 10, "iteration": 2})
    b = TraceWriter("repo_b__t1_only__seed0", trace_root=root)
    b.emit(
        "patch",
        {"source": "T1", "outcome": "applied", "files_changed": ["y.py"], "lines_changed": 20},
    )
    b.emit("llm_call", {"model": "m"}, tokens_in=1, tokens_out=1)  # unpriced
    b.emit("error", {"where": "repair", "message": "boom"})


def test_index_rebuild_summarises_each_run(tmp_path: Path) -> None:
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    assert rebuild(trace_root=tmp_path, index_path=idx) == 2

    runs = {r.run_id: r for r in list_runs(index_path=idx)}
    a = runs["repo_a__graph__seed0"]
    assert (a.last_passed, a.last_total) == (9, 10)
    assert a.llm_calls == 1 and a.usd == 0.05 and a.patches_applied == 1
    b = runs["repo_b__t1_only__seed0"]
    assert b.unpriced_calls == 1 and b.errors == 1


def test_index_is_rebuilt_from_scratch_not_migrated(tmp_path: Path) -> None:
    """The JSONL files are the source of truth; the index is a throw-away read model, so a
    second rebuild must not double-count (docs/decisions.md D95)."""
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    rebuild(trace_root=tmp_path, index_path=idx)
    rebuild(trace_root=tmp_path, index_path=idx)
    assert len(list_runs(index_path=idx)) == 2


def test_cost_breakdown_flags_unpriced_runs(tmp_path: Path) -> None:
    """A run that is cheap because nothing recorded its prices must not read as a cheap
    run (D90)."""
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    rebuild(trace_root=tmp_path, index_path=idx)
    by_run = {r: (usd, unpriced) for r, usd, unpriced in cost_breakdown(index_path=idx)}
    assert by_run["repo_b__t1_only__seed0"] == (0.0, 1)


def test_failure_class_distribution_aggregates_across_runs(tmp_path: Path) -> None:
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    rebuild(trace_root=tmp_path, index_path=idx)
    assert dict(failure_class_distribution(index_path=idx)) == {"import_error": 1, "unknown": 1}


def test_dashboard_renders_runs_costs_and_the_missing_diff_viewer_note(tmp_path: Path) -> None:
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    rebuild(trace_root=tmp_path, index_path=idx)
    page = render_dashboard(index_path=idx)

    assert "repo_a__graph__seed0" in page
    assert "9/10" in page
    assert "lower bound" in page  # unpriced call surfaced, not hidden
    assert "No diff viewer" in page  # the spec's tension, stated in the page itself


def test_dashboard_handles_an_empty_index(tmp_path: Path) -> None:
    page = render_dashboard(index_path=tmp_path / "absent.db")
    assert "No traced runs yet" in page


def test_write_dashboard_creates_the_file(tmp_path: Path) -> None:
    _traces(tmp_path)
    idx = tmp_path / "index.db"
    rebuild(trace_root=tmp_path, index_path=idx)
    out = write_dashboard(tmp_path / "sub" / "d.html", index_path=idx)
    assert out.exists() and out.read_text().startswith("<!doctype html>")
