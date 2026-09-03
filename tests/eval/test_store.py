from collections import Counter
from dataclasses import replace
from pathlib import Path

from pmigrate.agent.state import RepairAttempt
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.metrics import RepoResult, ScoredRepairAttempt
from pmigrate.eval.store import ResultStore, config_hash, corpus_sha
from pmigrate.types import FailureClass


def _config(**overrides: object) -> EvalConfig:
    kwargs: dict[str, object] = {"name": "graph", "model": "gemini-3.6-flash"}
    kwargs.update(overrides)
    return EvalConfig(**kwargs)  # type: ignore[arg-type]


def _result(repo_id: str = "acme__widgets", config: EvalConfig | None = None) -> RepoResult:
    attempt = RepairAttempt(
        iteration=1,
        cls=FailureClass.IMPORT_ERROR,
        strategy="fix_import",
        node_ids=("t.py::a",),
        outcome="applied",
        usd_cost=0.01,
    )
    return RepoResult(
        repo_id=repo_id,
        config=config or _config(),
        pass_rate=0.75,
        full_green=False,
        iterations=3,
        usd_spent=0.42,
        wallclock_s=12.5,
        final_diagnosis_counts=Counter({FailureClass.IMPORT_ERROR: 2}),
        avg_failures_per_diagnosis=1.5,
        scored_repairs=(ScoredRepairAttempt(attempt=attempt, fixed=True),),
        diff_line_jaccard=0.6,
        symbol_precision=0.8,
        symbol_recall=0.5,
        trace_path=None,
    )


def test_config_hash_is_stable_across_calls() -> None:
    assert config_hash(_config()) == config_hash(_config())


def test_config_hash_differs_for_different_configs() -> None:
    assert config_hash(_config()) != config_hash(_config(retrieval="wholefile"))


def test_config_hash_ignores_tiers_set_order() -> None:
    # frozenset iteration order isn't guaranteed -- the hash must be order-independent
    a = _config(tiers=frozenset({"T1", "T2", "T3"}))
    b = _config(tiers=frozenset({"T3", "T2", "T1"}))
    assert config_hash(a) == config_hash(b)


def test_corpus_sha_is_stable_for_the_same_bytes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('[{"repo_id": "a"}]')
    assert corpus_sha(manifest) == corpus_sha(manifest)


def test_corpus_sha_differs_when_the_file_changes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('[{"repo_id": "a"}]')
    sha_before = corpus_sha(manifest)
    manifest.write_text('[{"repo_id": "b"}]')
    assert corpus_sha(manifest) != sha_before


def test_has_result_is_false_before_any_save(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    assert store.has_result("acme__widgets", config_hash(_config()), "deadbeef") is False


def test_save_then_load_round_trips_the_full_result(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    result = _result()
    c_hash = config_hash(result.config)
    store.save_result(result, "deadbeef", written_at=100.0)

    assert store.has_result("acme__widgets", c_hash, "deadbeef") is True
    loaded = store.load_result("acme__widgets", c_hash, "deadbeef")
    assert loaded == result


def test_load_result_returns_none_for_an_unknown_cell(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    assert store.load_result("acme__widgets", "nohash", "deadbeef") is None


def test_different_corpus_sha_is_a_different_cell(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    result = _result()
    c_hash = config_hash(result.config)
    store.save_result(result, "sha-one", written_at=100.0)

    assert store.has_result("acme__widgets", c_hash, "sha-two") is False


def test_different_config_is_a_different_cell(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    result = _result()
    store.save_result(result, "deadbeef", written_at=100.0)

    other_hash = config_hash(_config(retrieval="wholefile"))
    assert store.has_result("acme__widgets", other_hash, "deadbeef") is False


def test_save_result_overwrites_an_existing_cell(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    result = _result()
    c_hash = config_hash(result.config)
    store.save_result(result, "deadbeef", written_at=100.0)

    updated = replace(result, pass_rate=1.0, full_green=True)
    store.save_result(updated, "deadbeef", written_at=200.0)

    loaded = store.load_result("acme__widgets", c_hash, "deadbeef")
    assert loaded is not None
    assert loaded.pass_rate == 1.0
    assert loaded.full_green is True


def test_a_result_with_no_repairs_or_diff_similarity_round_trips(tmp_path: Path) -> None:
    store = ResultStore(tmp_path / "results.db")
    result = RepoResult(
        repo_id="acme__widgets",
        config=_config(),
        pass_rate=1.0,
        full_green=True,
        iterations=1,
        usd_spent=0.0,
        wallclock_s=1.0,
        final_diagnosis_counts=Counter(),
        avg_failures_per_diagnosis=0.0,
        scored_repairs=(),
    )
    store.save_result(result, "deadbeef", written_at=1.0)

    loaded = store.load_result("acme__widgets", config_hash(result.config), "deadbeef")
    assert loaded == result
