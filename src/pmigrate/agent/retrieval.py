"""Phase 5's retrieval ablation (docs/phase-5-eval.md): what context does `repair()`
include alongside the target file when building its prompt? All three arms live here now
(docs/decisions.md D60/D61).

`Retrieval.related_files` matches `agent/repair.py`'s `find_related_files` exactly in
shape (same three params, same "extra file paths, not including target_path" contract) --
that function IS the default strategy (docs/decisions.md D28's grep heuristic), preserved
as `build_migration_graph`'s fallback when no `retrieval` is passed, so every existing
test keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pmigrate.graph.ir import ParsedClass
from pmigrate.graph.memory_store import InMemoryCodeGraph
from pmigrate.graph.relevance import find_pydantic_model_classes
from pmigrate.graph.repo_files import read_py_files
from pmigrate.graph.resolver import ResolvedRepo, resolve_repo
from pmigrate.graph.token_budget import truncate_to_budget
from pmigrate.types import RepoSpec, SymbolKind, SymbolRef

# Matches graph/memory_store.py's neighbourhood() default shape -- both budgets estimate
# from the same TOKENS_PER_LINE_ESTIMATE (token_budget.py), so this stays comparable
# across the two strategies rather than an arbitrarily different number per arm.
DEFAULT_BUDGET_TOKENS = 4000


class Retrieval(Protocol):
    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        """Extra file paths (relative to `repo_root`, NOT including `target_path`) to
        include as context in the repair prompt alongside the target file."""
        ...


@dataclass
class GraphRetrieval:
    """docs/phase-5-eval.md's "graph" arm -- wraps `CodeGraph.neighbourhood`
    (graph/protocol.py), whose own docstring calls it "the function Phase 5's retrieval
    ablation swaps out." Re-ingests a fresh `InMemoryCodeGraph` on every call rather than
    caching one, since `repo_root`'s content changes between `repair()` iterations as
    earlier edits land -- matching `find_related_files`'s own always-fresh-read behavior,
    not an oversight. Seeds the BFS from the target file's own MODULE symbol (CONTAINS
    edges reach its classes, IMPORTS edges reach imported modules) rather than one
    specific class, since a target FILE, not a single symbol, is what repair() actually
    wants context for."""

    repo_id: str
    budget_tokens: int = DEFAULT_BUDGET_TOKENS

    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        resolved = resolve_repo(read_py_files(repo_root))
        module_fqname = next(
            (fq for fq, path in resolved.module_paths.items() if path == target_path), None
        )
        if module_fqname is None:
            return ()

        graph = InMemoryCodeGraph()
        # ingest() only ever reads repo.repo_id off this argument (graph/memory_store.py)
        # -- every other RepoSpec field is meaningless for a one-off graph population
        # call, not a real corpus entry, so placeholders are correct here, not a shortcut.
        graph.ingest(
            RepoSpec(
                repo_id=self.repo_id,
                url="",
                pre_sha="",
                post_sha="",
                python_version="",
                install_cmd=(),
                test_cmd=(),
            ),
            repo_root,
        )

        target_ref = graph.get(self.repo_id, module_fqname)
        if target_ref is None:
            return ()

        neighbours = graph.neighbourhood(target_ref, self.budget_tokens)
        paths = {n.path for n in neighbours if n.path != target_path}
        return tuple(sorted(paths))


@dataclass
class WholefileRetrieval:
    """docs/phase-5-eval.md's "wholefile" arm -- every pydantic-touching file (the same
    signal `graph/relevance.py`'s `find_pydantic_model_classes` gives `compute_work_list`
    for T1's own file selection), truncated to a token budget via the same
    `truncate_to_budget` `GraphRetrieval` uses -- applied to whole files (start_line=1,
    end_line=file length) instead of graph neighbours. Answers phase-5-eval.md's own
    question: "is retrieval needed at all, or does a big context window solve it?"."""

    budget_tokens: int = DEFAULT_BUDGET_TOKENS

    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        files = read_py_files(repo_root)
        resolved = resolve_repo(files)
        model_classes = find_pydantic_model_classes(resolved)
        touched_paths = sorted(
            {resolved.module_paths[fq] for fq, _cls_name in model_classes} - {target_path}
        )

        candidates = []
        for path in touched_paths:
            content = files.get(path, b"").decode("utf-8", errors="replace")
            line_count = len(content.splitlines()) or 1
            candidates.append(
                SymbolRef(
                    repo_id="",
                    fqname=path,
                    kind=SymbolKind.MODULE,
                    path=path,
                    start_line=1,
                    end_line=line_count,
                )
            )

        return tuple(c.path for c in truncate_to_budget(candidates, self.budget_tokens))


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per input text, same order in, same order out."""
        ...


@dataclass
class SentenceTransformerEmbedder:
    """docs/decisions.md D61: local, real embeddings via `sentence-transformers`
    (`all-MiniLM-L6-v2` by default) -- no API key, no quota, no per-call cost, works
    offline, chosen specifically to avoid a FOURTH provider-quota crisis after Gemini's
    trickle-refill (D48) and Groq's daily-token exhaustion (D53) both hit this project the
    same day. `sentence-transformers` (which pulls in `torch`) is an OPTIONAL dependency
    (`pyproject.toml`'s `embedding` extra, `pip install -e .[embedding]`) -- most of this
    project (T1, triage, the other two retrieval arms) has no reason to force a
    multi-hundred-MB install, so the import is lazy, inside `embed()`, not at module load
    time; only actually constructing and calling this specific class pays that cost."""

    model_name: str = "all-MiniLM-L6-v2"
    _model: object | None = field(default=None, init=False, repr=False)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            try:
                import sentence_transformers  # type: ignore[import-not-found]
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is not installed -- run "
                    "`pip install -e '.[embedding]'` to use EmbeddingRetrieval"
                ) from exc
            self._model = sentence_transformers.SentenceTransformer(self.model_name)
        embeddings: list[list[float]] = self._model.encode(texts).tolist()  # type: ignore[attr-defined]
        return embeddings


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain Python, no numpy -- keeps this module importable, and `EmbeddingRetrieval`'s
    chunking/ranking logic unit-testable with a fake `Embedder`, without installing the
    `embedding` extra at all. Only `SentenceTransformerEmbedder.embed` itself needs the
    heavy dependency, and only when actually called."""
    dot: float = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a: float = sum(x * x for x in a) ** 0.5
    norm_b: float = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _symbol_chunks(
    resolved: ResolvedRepo, files: dict[str, bytes], exclude_path: str
) -> list[tuple[SymbolRef, str]]:
    """Every class/nested class/method/function across the WHOLE repo as (SymbolRef, own
    source text) pairs -- the chunking unit `EmbeddingRetrieval` embeds, matching the same
    symbol boundaries `GraphRetrieval`/`WholefileRetrieval` already operate on rather than
    a separately invented line/character-based chunker. Lives here, not reused from
    `eval/diff_similarity.py`'s similarly-shaped `_symbol_ranges`, because that function is
    file-scoped and range-only (diffing two versions of ONE file); this is repo-scoped and
    needs each symbol's actual TEXT to embed -- a different problem, not a duplicated one,
    and `agent/` can't import from `eval/` without inverting this project's layering
    (`eval/harness.py` already imports FROM `agent/`, never the other way)."""
    chunks: list[tuple[SymbolRef, str]] = []
    for module_fqname, module in resolved.modules.items():
        path = resolved.module_paths[module_fqname]
        if path == exclude_path:
            continue
        lines = files.get(path, b"").decode("utf-8", errors="replace").splitlines()

        def _text_for(start: int, end: int, _lines: list[str] = lines) -> str:
            return "\n".join(_lines[start - 1 : end])

        def _walk_class(
            cls: ParsedClass, prefix: str, _path: str = path, _lines: list[str] = lines
        ) -> None:
            qualified = f"{prefix}.{cls.name}" if prefix else cls.name
            for nested in cls.nested_classes:
                _walk_class(nested, qualified, _path, _lines)
            for method in cls.methods:
                chunks.append(
                    (
                        SymbolRef(
                            repo_id="",
                            fqname=f"{_path}::{qualified}.{method.name}",
                            kind=SymbolKind.METHOD,
                            path=_path,
                            start_line=method.start_line,
                            end_line=method.end_line,
                        ),
                        _text_for(method.start_line, method.end_line, _lines),
                    )
                )
            chunks.append(
                (
                    SymbolRef(
                        repo_id="",
                        fqname=f"{_path}::{qualified}",
                        kind=SymbolKind.CLASS,
                        path=_path,
                        start_line=cls.start_line,
                        end_line=cls.end_line,
                    ),
                    _text_for(cls.start_line, cls.end_line, _lines),
                )
            )

        for cls in module.classes:
            _walk_class(cls, "")
        for func in module.functions:
            chunks.append(
                (
                    SymbolRef(
                        repo_id="",
                        fqname=f"{path}::{func.name}",
                        kind=SymbolKind.FUNCTION,
                        path=path,
                        start_line=func.start_line,
                        end_line=func.end_line,
                    ),
                    _text_for(func.start_line, func.end_line),
                )
            )
    return chunks


@dataclass
class EmbeddingRetrieval:
    """docs/phase-5-eval.md's "embedding" arm -- retrieval = cosine similarity over
    embeddings of each symbol's own source text (one chunk per function/class/method,
    `_symbol_chunks` above), ranked and truncated to a token budget via the SAME
    `truncate_to_budget` the other two arms use (comparable budgets across all three, not
    an arbitrarily different number per arm). Brute-force similarity over a small,
    in-memory list -- not a real vector database -- since corpus repos here are tens to a
    few hundred files, well within "a for loop is fine" territory (the same reasoning
    `graph/memory_store.py`'s own in-memory graph backend already gives for itself).

    `embedder` is injected (docs/decisions.md D61), not constructed internally, matching
    `ModelClient`/`Sandbox`'s existing real-vs-fake split: a real `SentenceTransformerEmbedder`
    in production, a scripted fake in tests -- loading a real model needs network on first
    use (a HuggingFace download), which `CLAUDE.md`'s "no network in unit tests" rule
    rules out for the default test suite.
    """

    embedder: Embedder
    budget_tokens: int = DEFAULT_BUDGET_TOKENS

    def related_files(
        self, target_path: str, target_before: str, repo_root: Path
    ) -> tuple[str, ...]:
        files = read_py_files(repo_root)
        resolved = resolve_repo(files)
        chunks = _symbol_chunks(resolved, files, exclude_path=target_path)
        if not chunks:
            return ()

        texts = [text for _ref, text in chunks] + [target_before]
        vectors = self.embedder.embed(texts)
        query_vector = vectors[-1]
        chunk_vectors = vectors[:-1]

        ranked = sorted(
            zip(chunks, chunk_vectors, strict=True),
            key=lambda pair: -_cosine_similarity(query_vector, pair[1]),
        )
        ranked_refs = [ref for (ref, _text), _vec in ranked]

        truncated = truncate_to_budget(ranked_refs, self.budget_tokens)
        paths: list[str] = []
        for ref in truncated:
            if ref.path not in paths:
                paths.append(ref.path)
        return tuple(paths)
