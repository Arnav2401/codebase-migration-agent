import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from pmigrate.agent.retrieval import (
    EmbeddingRetrieval,
    SentenceTransformerEmbedder,
    _cosine_similarity,
)


@dataclass
class FakeEmbedder:
    """Deterministic, no ML/network: maps each text to a fixed vector via a lookup keyed
    by a recognizable substring, so a test can control similarity ranking precisely
    without a real model (which needs network on first use -- CLAUDE.md's "no network in
    unit tests" rule). Falls back to an all-zero vector (similarity 0.0 to everything,
    including another all-zero vector, since `_cosine_similarity` treats a zero norm as
    0.0 rather than dividing by zero) for any text that doesn't match a known marker."""

    vectors_by_marker: dict[str, list[float]]
    calls: list = field(default_factory=list)

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        result = []
        for text in texts:
            vec = next(
                (v for marker, v in self.vectors_by_marker.items() if marker in text),
                [0.0, 0.0],
            )
            result.append(vec)
        return result


def _setup_repo(tmp_path: Path) -> Path:
    app = tmp_path / "app"
    app.mkdir()
    (app / "models.py").write_text(
        "class AppSettings:\n    def validate_config(self):\n        return True\n"
    )
    (app / "close_match.py").write_text("def validate_something():\n    return True\n")
    (app / "far_match.py").write_text("def unrelated_helper():\n    return 42\n")
    return tmp_path


def test_cosine_similarity_is_one_for_identical_vectors() -> None:
    assert _cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0


def test_cosine_similarity_is_zero_for_a_zero_vector() -> None:
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_is_zero_for_orthogonal_vectors() -> None:
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_embedding_retrieval_ranks_the_most_similar_symbol_first(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    # the target's own text embeds to [1, 0]; close_match's function embeds near it;
    # far_match embeds orthogonally.
    embedder = FakeEmbedder(
        vectors_by_marker={
            "validate_config": [1.0, 0.0],
            "validate_something": [0.9, 0.1],
            "unrelated_helper": [0.0, 1.0],
        }
    )
    retrieval = EmbeddingRetrieval(embedder=embedder, budget_tokens=10_000)

    related = retrieval.related_files("app/models.py", target_before, root)

    assert related[0] == "app/close_match.py"
    assert "app/far_match.py" in related  # still included, just ranked lower


def test_embedding_retrieval_excludes_the_target_path(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    embedder = FakeEmbedder(vectors_by_marker={})
    retrieval = EmbeddingRetrieval(embedder=embedder, budget_tokens=10_000)

    related = retrieval.related_files("app/models.py", target_before, root)

    assert "app/models.py" not in related


def test_embedding_retrieval_respects_a_tiny_budget(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    embedder = FakeEmbedder(vectors_by_marker={})
    retrieval = EmbeddingRetrieval(embedder=embedder, budget_tokens=1)

    related = retrieval.related_files("app/models.py", target_before, root)

    assert len(related) <= 1


def test_embedding_retrieval_returns_empty_when_no_other_symbols_exist(tmp_path: Path) -> None:
    root = tmp_path
    (root / "app").mkdir()
    (root / "app" / "models.py").write_text("x = 1\n")  # no classes/functions at all
    embedder = FakeEmbedder(vectors_by_marker={})
    retrieval = EmbeddingRetrieval(embedder=embedder, budget_tokens=10_000)

    related = retrieval.related_files("app/models.py", "x = 1\n", root)

    assert related == ()
    assert embedder.calls == []  # never even called the embedder with nothing to embed


class _FakeEncoded:
    def __init__(self, n: int) -> None:
        self._n = n

    def tolist(self) -> list[list[float]]:
        return [[0.0] for _ in range(self._n)]


def test_sentence_transformer_embedder_serializes_concurrent_embed_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """docs/decisions.md D67: the real live-run crash (`eval/harness.py`'s `run_corpus`
    under `max_workers>1`) was multiple worker threads racing to construct
    `SentenceTransformer(...)` concurrently -- each on its OWN `SentenceTransformerEmbedder`
    instance, since `_build_retrieval` built a fresh one per repo. This test exercises the
    REAL fixed `SentenceTransformerEmbedder.embed()` (not a reimplementation) against a
    fake `sentence_transformers` module standing in for the real one (heavy, needs network
    on first use -- CLAUDE.md's "no network in unit tests" rule), and proves its `_lock`
    actually serializes concurrent `.embed()` calls on ONE shared instance: without the
    lock, two threads could both observe `constructing=False` before either sets it, so
    `overlap_detected` would go `True` and `construct_count` would exceed 1 -- exactly the
    race the live crash needed."""
    overlap_detected = False
    constructing = False
    construct_count = 0
    state_lock = threading.Lock()

    class FakeSentenceTransformer:
        def __init__(self, model_name: str) -> None:
            nonlocal overlap_detected, constructing, construct_count
            with state_lock:
                if constructing:
                    overlap_detected = True
                constructing = True
                construct_count += 1
            time.sleep(0.05)  # widen the race window a lock-less version would fall into
            with state_lock:
                constructing = False

        def encode(self, texts: list[str]) -> _FakeEncoded:
            return _FakeEncoded(len(texts))

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    embedder = SentenceTransformerEmbedder()
    n_threads = 8
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [executor.submit(embedder.embed, ["x"]) for _ in range(n_threads)]
        for future in futures:
            future.result()

    assert construct_count == 1
    assert overlap_detected is False
