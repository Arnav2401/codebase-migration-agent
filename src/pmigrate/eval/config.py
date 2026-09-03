"""Phase 5's ablation-arm data contract (docs/interfaces.md §8, docs/phase-5-eval.md).

The full field set is settled now -- every arm phase-5-eval.md names needs SOME identifier
for `retrieval`/`tiers`, and the shape is already agreed in interfaces.md -- but only
`model`/`triage`/`seed`/`usd_cap_per_repo`/`retrieval` are actually wired into behavior.
As of docs/decisions.md D60/D61, all three `retrieval` kinds are real: `"graph"`
(`agent/retrieval.py`'s `GraphRetrieval`), `"wholefile"` (`WholefileRetrieval`), and
`"embedding"` (`EmbeddingRetrieval`, local `sentence-transformers` -- an optional
dependency, `pyproject.toml`'s `embedding` extra). `tiers` still exists only so a config
can be constructed and referenced meaningfully in results and run manifests going
forward; requesting anything but the full T1+T2+T3 set raises `NotImplementedError`
rather than silently running the wrong thing -- T1/T2/T3 gating in `agent/graph.py` is
its own later step, not guessed at here.

`RetrievalKind` (this module) is a plain string-literal type -- deliberately NOT named
`Retrieval`, which is `agent/retrieval.py`'s actual behavioral Protocol (`related_files`).
Matches this codebase's own `SymbolKind`/`EdgeKind` naming convention for "a literal tag,
not a class with behavior."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RetrievalKind = Literal["graph", "embedding", "wholefile"]
Tier = Literal["T1", "T2", "T3"]

_ALL_TIERS: frozenset[Tier] = frozenset({"T1", "T2", "T3"})
_IMPLEMENTED_RETRIEVAL_KINDS: frozenset[RetrievalKind] = frozenset(
    {"graph", "wholefile", "embedding"}
)


@dataclass(frozen=True)
class EvalConfig:
    name: str
    model: str
    retrieval: RetrievalKind = "graph"
    tiers: frozenset[Tier] = field(default_factory=lambda: _ALL_TIERS)
    triage: bool = True
    seed: int = 0
    usd_cap_per_repo: float = 5.0

    def __post_init__(self) -> None:
        if self.retrieval not in _IMPLEMENTED_RETRIEVAL_KINDS:
            raise NotImplementedError(
                f"retrieval={self.retrieval!r} is not implemented yet -- only "
                f"{sorted(_IMPLEMENTED_RETRIEVAL_KINDS)} run today"
            )
        if self.tiers != _ALL_TIERS:
            raise NotImplementedError(
                f"tiers={set(self.tiers)!r} is not implemented yet -- only the full "
                "T1+T2+T3 set runs today, gating individual tiers is a later Phase 5 step"
            )
