"""Budget enforcement (docs/interfaces.md §5, docs/phase-3-loop.md "Budget guards").
Checked at every node entry in the migration loop: a run that costs $40 because it looped
is worse than a run that fails cleanly at $2. `BudgetState` is immutable — each check-in
point produces a new state via `spend`/`next_iteration`, so the trace (Phase 6) can log
budget state at every step without any node mutating shared state out from under another.

Also home to the no-progress detector (docs/phase-3-loop.md): "hash the sorted set of
failing node ids; if the same hash appears twice in a row after a repair, the strategy
isn't working — escalate ... or abort." Kept here rather than in triage/ since it's a
budget-adjacent circuit breaker, not a classification concern.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

BreachedLimit = str  # "usd_cap" | "max_iterations" | "wallclock_cap" — kept as a plain str
# rather than a Literal, since Phase 6's trace just needs to log whatever string comes back


@dataclass(frozen=True)
class BudgetState:
    usd_spent: float = 0.0
    usd_cap: float = 5.0
    tokens_in: int = 0
    tokens_out: int = 0
    iterations: int = 0
    max_iterations: int = 20
    started_at: float = field(default_factory=time.time)
    wallclock_cap_s: int = 1800

    def exceeded(self) -> BreachedLimit | None:
        if self.usd_spent > self.usd_cap:
            return "usd_cap"
        if self.iterations > self.max_iterations:
            return "max_iterations"
        if time.time() - self.started_at > self.wallclock_cap_s:
            return "wallclock_cap"
        return None

    def spend(self, usd: float, tokens_in: int = 0, tokens_out: int = 0) -> BudgetState:
        return replace(
            self,
            usd_spent=self.usd_spent + usd,
            tokens_in=self.tokens_in + tokens_in,
            tokens_out=self.tokens_out + tokens_out,
        )

    def next_iteration(self) -> BudgetState:
        return replace(self, iterations=self.iterations + 1)


def failure_signature(failing_node_ids: Iterable[str]) -> str:
    """A stable fingerprint of which tests are failing, independent of order — used to
    detect "the same failures came back after a repair attempt", not "these are the exact
    same objects"."""
    joined = "\n".join(sorted(failing_node_ids))
    return hashlib.sha256(joined.encode()).hexdigest()


@dataclass
class NoProgressDetector:
    """Stateful by design (unlike BudgetState) — it exists specifically to remember what
    happened across repair attempts within one node's retry loop, which is exactly the
    kind of local, short-lived state that doesn't need to survive in the trace on its own
    (the TestRun history it's derived from does)."""

    repeat_threshold: int = 2
    _last_signature: str | None = field(default=None, repr=False)
    _repeat_count: int = field(default=0, repr=False)

    def observe(self, failing_node_ids: Iterable[str]) -> bool:
        """Returns True once the same failure signature has recurred `repeat_threshold`
        times in a row — the signal to escalate strategy or abort repair."""
        signature = failure_signature(failing_node_ids)
        if signature == self._last_signature:
            self._repeat_count += 1
        else:
            self._last_signature = signature
            self._repeat_count = 1
        return self._repeat_count >= self.repeat_threshold

    def reset(self) -> None:
        self._last_signature = None
        self._repeat_count = 0
