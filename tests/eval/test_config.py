import pytest

from pmigrate.eval.config import EvalConfig


def test_default_config_constructs_with_the_currently_implemented_axes() -> None:
    config = EvalConfig(name="graph", model="gemini-3.6-flash")
    assert config.retrieval == "graph"
    assert config.tiers == frozenset({"T1", "T2", "T3"})
    assert config.triage is True
    assert config.seed == 0


def test_triage_off_config_constructs_fine() -> None:
    config = EvalConfig(name="no_triage", model="gemini-3.6-flash", triage=False)
    assert config.triage is False


def test_wholefile_retrieval_config_constructs_fine() -> None:
    # docs/decisions.md D60: wholefile joined graph as a real, implemented retrieval kind
    config = EvalConfig(name="wholefile", model="gemini-3.6-flash", retrieval="wholefile")
    assert config.retrieval == "wholefile"


def test_embedding_retrieval_config_constructs_fine() -> None:
    # docs/decisions.md D61: embedding joined graph/wholefile as a real, implemented
    # retrieval kind (local sentence-transformers, an optional dependency -- constructing
    # the config itself needs no heavy import at all, only actually calling
    # EmbeddingRetrieval.related_files does).
    config = EvalConfig(name="embedding", model="gemini-3.6-flash", retrieval="embedding")
    assert config.retrieval == "embedding"


def test_unimplemented_retrieval_kind_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="retrieval"):
        EvalConfig(name="bad", model="gemini-3.6-flash", retrieval="not_a_real_kind")  # type: ignore[arg-type]


def test_t1_only_tier_set_constructs_fine() -> None:
    # docs/decisions.md D62: t1_only became a real, implemented arm
    config = EvalConfig(name="t1_only", model="gemini-3.6-flash", tiers=frozenset({"T1"}))
    assert config.tiers == frozenset({"T1"})


def test_no_t1_tier_set_constructs_fine() -> None:
    # docs/decisions.md D62: no_t1 became a real, implemented arm
    config = EvalConfig(name="no_t1", model="gemini-3.6-flash", tiers=frozenset({"T2", "T3"}))
    assert config.tiers == frozenset({"T2", "T3"})


def test_t2_alone_raises_not_implemented() -> None:
    # repair() fuses T2 and T3 into one node -- no config can honor a request naming one
    # but not the other (docs/decisions.md D62)
    with pytest.raises(NotImplementedError, match="tiers"):
        EvalConfig(name="t2_only", model="gemini-3.6-flash", tiers=frozenset({"T2"}))


def test_t1_and_t2_without_t3_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="tiers"):
        EvalConfig(name="t1_t2_only", model="gemini-3.6-flash", tiers=frozenset({"T1", "T2"}))


def test_config_is_hashable_for_future_resumability_keying() -> None:
    # phase-5-eval.md: "store results in SQLite keyed by (repo_id, config_hash,
    # corpus_sha)" -- a later step, but the type needs to support it now.
    config = EvalConfig(name="graph", model="gemini-3.6-flash")
    hash(config)  # must not raise
