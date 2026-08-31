"""Shared by every CodeGraph backend's `neighbourhood()` so the token-budget heuristic is
defined once. No backend retains source text (only line ranges), so this estimates cost
from symbol size rather than counting real tokens — a deliberate approximation, not a
precise budget. ~8 tokens/line is a rough average for Python; revisit once Phase 3 has
real token counts from actual model calls to compare against.
"""

from __future__ import annotations

from pmigrate.types import SymbolRef

TOKENS_PER_LINE_ESTIMATE = 8


def truncate_to_budget(candidates: list[SymbolRef], budget_tokens: int) -> list[SymbolRef]:
    result: list[SymbolRef] = []
    used = 0
    for c in candidates:
        cost = max(1, c.end_line - c.start_line + 1) * TOKENS_PER_LINE_ESTIMATE
        if result and used + cost > budget_tokens:
            break
        result.append(c)
        used += cost
    return result
