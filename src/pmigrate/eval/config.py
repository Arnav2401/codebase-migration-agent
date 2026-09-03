"""Phase 5's ablation-arm data contract (docs/interfaces.md §8, docs/phase-5-eval.md).

The full field set is settled now -- every arm phase-5-eval.md names needs SOME identifier
for `retrieval`/`tiers`, and the shape is already agreed in interfaces.md -- but only
`model`/`triage`/`seed`/`usd_cap_per_repo` are actually wired into behavior yet.
`retrieval`/`tiers` exist so a config can be constructed and referenced meaningfully in
results and run manifests going forward; requesting anything other than today's implicit
values raises `NotImplementedError` rather than silently running the wrong thing. Each
gets built out (a real `Retrieval` protocol, T1/T2/T3 gating in `agent/graph.py`) in its
own later step, not guessed at here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Retrieval = Literal["graph", "embedding", "wholefile"]
Tier = Literal["T1", "T2", "T3"]

_ALL_TIERS: frozenset[Tier] = frozenset({"T1", "T2", "T3"})


@dataclass(frozen=True)
class EvalConfig:
    name: str
    model: str
    retrieval: Retrieval = "graph"
    tiers: frozenset[Tier] = field(default_factory=lambda: _ALL_TIERS)
    triage: bool = True
    seed: int = 0
    usd_cap_per_repo: float = 5.0

    def __post_init__(self) -> None:
        if self.retrieval != "graph":
            raise NotImplementedError(
                f"retrieval={self.retrieval!r} is not implemented yet -- only 'graph' "
                "(the Phase 1 CodeGraph-backed work_list) runs today"
            )
        if self.tiers != _ALL_TIERS:
            raise NotImplementedError(
                f"tiers={set(self.tiers)!r} is not implemented yet -- only the full "
                "T1+T2+T3 set runs today, gating individual tiers is a later Phase 5 step"
            )
