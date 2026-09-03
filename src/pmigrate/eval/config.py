"""Phase 5's ablation-arm data contract (docs/interfaces.md §8, docs/phase-5-eval.md).

The full field set is settled now -- every arm phase-5-eval.md names needs SOME identifier
for `retrieval`/`tiers`, and the shape is already agreed in interfaces.md -- but only
`model`/`triage`/`seed`/`usd_cap_per_repo`/`retrieval` are actually wired into behavior.
As of docs/decisions.md D60/D61, all three `retrieval` kinds are real: `"graph"`
(`agent/retrieval.py`'s `GraphRetrieval`), `"wholefile"` (`WholefileRetrieval`), and
`"embedding"` (`EmbeddingRetrieval`, local `sentence-transformers` -- an optional
dependency, `pyproject.toml`'s `embedding` extra). As of docs/decisions.md D62, `tiers`
selects one of three real arms: the full `{"T1","T2","T3"}` set (default), `{"T1"}`
("t1_only" -- `run_repo` forces
`model_client=None`, matching `agent/graph.py`'s existing "no client means no repair"
behavior), or `{"T2","T3"}` ("no_t1" -- `run_repo` passes `enable_t1=False`). Any OTHER
combination raises `NotImplementedError` rather than silently running the wrong thing:
`repair()` fuses T2 and T3 into one node (no `source="T3"` is ever constructed anywhere
in the codebase), so there is no way to honor a request that includes one but not the
other -- `{"T2"}` alone is not a real, distinguishable arm today.

`RetrievalKind` (this module) is a plain string-literal type -- deliberately NOT named
`Retrieval`, which is `agent/retrieval.py`'s actual behavioral Protocol (`related_files`).
Matches this codebase's own `SymbolKind`/`EdgeKind` naming convention for "a literal tag,
not a class with behavior."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RetrievalKind = Literal["graph", "embedding", "wholefile"]
Tier = Literal["T1", "T2", "T3"]

_ALL_TIERS: frozenset[Tier] = frozenset({"T1", "T2", "T3"})
_T1_ONLY: frozenset[Tier] = frozenset({"T1"})
_NO_T1: frozenset[Tier] = frozenset({"T2", "T3"})
_IMPLEMENTED_TIER_SETS: frozenset[frozenset[Tier]] = frozenset({_ALL_TIERS, _T1_ONLY, _NO_T1})
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
        if self.tiers not in _IMPLEMENTED_TIER_SETS:
            raise NotImplementedError(
                f"tiers={set(self.tiers)!r} is not implemented yet -- only "
                f"{sorted(sorted(t) for t in _IMPLEMENTED_TIER_SETS)} run today "
                "(T2 and T3 share one node in agent/graph.py's repair(), so any set "
                "naming one but not the other can't be honored)"
            )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe encoding (docs/decisions.md D63): `tiers` is a frozenset, not
        JSON-native, so `dataclasses.asdict` alone can't round-trip this type -- lives
        here, not in `eval/store.py`/`eval/manifest.py`, since both need the exact same
        encoding and this is the type that owns what its own fields mean."""
        return {
            "name": self.name,
            "model": self.model,
            "retrieval": self.retrieval,
            "tiers": sorted(self.tiers),
            "triage": self.triage,
            "seed": self.seed,
            "usd_cap_per_repo": self.usd_cap_per_repo,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EvalConfig:
        return EvalConfig(
            name=data["name"],
            model=data["model"],
            retrieval=data["retrieval"],
            tiers=frozenset(data["tiers"]),
            triage=data["triage"],
            seed=data["seed"],
            usd_cap_per_repo=data["usd_cap_per_repo"],
        )
