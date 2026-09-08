"""Phase 6b: the PR workflow (docs/phase-6-trace-pr.md).

Fork-only by construction (invariant I7). The PR body is generated from the run's trace,
which is the second job the trace does for its keep: if a body can only be written from the
trace, the trace demonstrably contains the run.
"""

from pmigrate.pr.allowlist import ForkTargetError, assert_allowed_target, is_allowed_target
from pmigrate.pr.body import PrPlan, build_pr_body, plan_from_trace

__all__ = [
    "ForkTargetError",
    "PrPlan",
    "assert_allowed_target",
    "build_pr_body",
    "is_allowed_target",
    "plan_from_trace",
]
