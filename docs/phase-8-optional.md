# Phase 8 — Optional extensions

**Locked until Phases 1–7 are done. Four components done properly beats ten done partially.**

## Semgrep / Bandit security regression gate (~2 days)

Run Semgrep before and after the migration; fail the run if the security posture worsened.
Cheap, and it turns "the tests pass" into "the tests pass and I didn't introduce a
vulnerability." Report it as an additional gate in the eval table, not as a headline.

## MCP server (~2 days)

Wrap the tool surface (`search_symbol`, `get_dependents`, `run_tests`, `apply_patch`,
`triage`) as an MCP server so any MCP client can drive the migration. The argument: you
built a capability, not an app — other systems can consume it. Genuinely a weekend, and it
demos well.

## LoRA distillation (~1 week) — last, or not at all

Your agent generates `(failure log + retrieved context → working patch)` pairs as a
byproduct of every eval run. By the end of Phase 5 you have thousands.

1. Extract pairs from the traces, filtered to patches that actually turned a test green.
2. Fine-tune a small open model (Qwen-Coder / Llama) with LoRA on them.
3. Slot it in as a Phase 5 model arm and compare accuracy, p95 latency, and cost per repo
   against the frontier API.

This is a real flywheel — the system's own output improves it — and it covers the
training-depth gap on your resume. But it's worth zero if Phases 1–5 aren't solid, because
you'd be distilling a bad teacher. Do it last.
