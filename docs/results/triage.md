# Phase 4 results: does triage-routed repair actually help?

**Run date:** 2026-09-03. **Model backend:** Groq `openai/gpt-oss-120b` (docs/decisions.md
D48/D49 — Gemini's free tier turned out to trickle-refill rather than reset daily,
impractical for a real run; Groq's key measured 1000 req/min of headroom). **Corpus:** 7
repos, `corpus/manifest.json`, dev split — 5 original plus 2 (`cmudig__draco2`,
`okfn__opendataeditor`) added to the manifest mid-session; this is the first writeup to
cover all 7. **Budget:** `usd_cap=1.0`, `max_iterations=8` per repo (per-repo caps; some
repos ran one iteration over `max_iterations` where the graph's own loop condition allows
one more classify pass after the last repair). **Code state:** every fix from D40 through
D50 applied, including D50's fix to `repair()`'s target-selection fallback (see below) —
this is the first run where the harness, sandbox overlay, scoring, and repair-target
fallback were all simultaneously correct.

This is a small corpus (7 repos) run once per arm — real numbers, not a statistically
robust study. Treat the comparison as a first, honest signal, not a final verdict. One
cell is missing: `okfn__opendataeditor`'s `use_triage=False` run hung (see below) and was
killed rather than left to block the rest of the corpus.

## Headline comparison: `use_triage=True` vs `use_triage=False`

`use_triage` (docs/decisions.md D40) is the one ablation axis built so far: with it off,
`repair()` falls back to the pre-D38 shape — every raw failure dumped into one prompt,
no per-class routing, no PREEXISTING skip in `route()`.

| Repo | pass_rate (ON) | pass_rate (OFF) | usd (ON) | usd (OFF) | iters (ON/OFF) | What happened |
|---|---|---|---|---|---|---|
| `madkote__fastapi-plugins` | 0.5185 | 0.5185 | $0.0018 | $0.0023 | 3 / 3 | **Identical.** This was the one repo where ON used to lose (0.37 vs 0.52) — D50 fixed the underlying bug; see below |
| `SupImDos__pydantic-argparse` | 0.00 | 0.00 | $0.0081 | $0.0074 | 9 / 9 | Genuinely hard case either way — `pydantic.fields.ModelField` has no 1:1 v2 equivalent. 8 real repair attempts per arm, all honest failures |
| `Aiven-Open__rohmu` | 0.8923 | 0.8615 | $0.0052 | $0.0021 | 4 / 2 | ON slightly ahead this run. ON hit a `413` on its 4th attempt after 3 real fixes; OFF hit its `413` earlier (2nd attempt), so it banked fewer fixes |
| `iscc__iscc-core` | 1.00 | 1.00 | $0.0000 | $0.0024 | 1 / 2 | No repair needed on ON; OFF made one unnecessary repair attempt (already green) that didn't change the outcome |
| `eyurtsev__kor` | 0.9551 | 0.5056 | $0.0014 | $0.0013 | 2 / 2 | ON's clearest win, reproduced cleanly from the earlier run — OFF's combined-failure prompt fixes less per call |
| `cmudig__draco2` *(new)* | 0.8777 | 0.8777 | $0.0010 | $0.0000 | 2 / 1 | **Same score, different reasons** — see below |
| `okfn__opendataeditor` *(new)* | 0.0217 | **unmeasured — infra issue** | $0.0000 | — | 1 / killed (x2) | ON completed (near-total failure — see below). OFF hung on **two separate attempts**, isolated reruns included — see below |

**Average pass rate, original 5 repos only (directly comparable to the previous writeup):
0.6672 (ON) vs 0.5771 (OFF)** — up from 0.640/0.578 pre-D50. **Average pass rate, all 7
repos, ON arm only (OFF incomplete): 0.6743.**

## The `madkote` regression was a real bug — now fixed (D50)

The previous version of this doc reported ON *losing* to OFF here (0.37 vs 0.52) and
described it as "a genuine edge case, not a triage design flaw." That framing undersold
it: it was a real bug in `repair()`'s target-selection fallback, `agent/graph.py`. The old
`_select_repair_target` picked only the single top-priority `GroupedDiagnosis` and gave up
entirely — `agent.repair_no_target`, no model call at all — if `extract_target_file` found
no target for it, even when a lower-priority diagnosis had a perfectly good target
available. `docs/decisions.md` D50 replaces this with
`_repair_candidates_in_priority_order`, which loops through candidates in priority order
and only gives up once none of them yield a target. This run confirms the fix: ON now
matches OFF exactly (0.5185 both arms) — one `validation_behaviour` repair applied to
`fastapi_plugins/logger.py`, then a legitimate `repair_no_target` on the next diagnosis
(which really has no fixable target), same outcome either way.

## Why triage still wins: `eyurtsev__kor`

This is the cleanest reproduction of the core argument. `use_triage=False` builds its
prompt from `collect_failure_texts()`, concatenating *every* raw failure's full text into
one prompt. `use_triage=True` picks exactly one `GroupedDiagnosis`
(`agent/graph.py`'s `_REPAIR_PRIORITY`) and sends only that diagnosis's raw failures —
smaller by construction, focused on one fixable problem. On `kor`, ON's single targeted
repair to `kor/extraction/parser.py` unblocks 40 additional tests (0.51 → 0.96); OFF's
combined prompt fixes something too, but less effectively (0.51 final). This is the
argument `docs/phase-4-triage.md` makes for why triage should matter, backed by a real,
reproduced number.

## `cmudig__draco2`: same score, different reasons

Worth reporting because the identical 0.8777 in both arms is a coincidence, not evidence
the two approaches are equivalent here. In the **ON** arm, the chosen diagnosis's repair
call returned a rewrite for a file the model was never shown (`agent.repair_unknown_path`)
— a real hallucination, safely discarded by the same apply_patch chokepoint that enforces
I1-I3 (never trust an unshown path enough to write to it). No edit was applied, and the
2nd iteration confirmed nothing changed. In the **OFF** arm, the combined-failure prompt
was large enough to hit Groq's `413 Payload Too Large` before the model ever saw it — the
same failure mode documented for `kor` and `rohmu` below, just landing on a repo where it
happened to produce the same final score as ON's unrelated failure. Two different bugs,
one coincidental tie.

## `okfn__opendataeditor`: hardest case in the corpus, and an incomplete run

The **ON** arm completed: pass_rate 0.0217 (2/92 tests passing after T1, one repair
attempt that hit a `413 Payload Too Large` and made no further progress). This looks like
a genuinely hard repo — T1's mechanical rewrite alone leaves it almost entirely broken —
rather than a harness bug, but with only one data point it's not yet possible to say
whether triage or the model backend could do meaningfully better with more budget.

The **OFF** arm did not complete, on either attempt. On the full corpus run, it got
through T1 and the first test run (also 2/92), then hung after the classify step with no
log output and no CPU progress for over 10 minutes — a single stalled HTTPS connection to
Groq's API sat in `CLOSE_WAIT`. A targeted, isolated rerun of just this one repo/arm
combination (`scratchpad/rerun_opendataeditor_off.py`, so a repeat hang couldn't block
anything else) reached the exact same point — T1 applied, 2/92 passing, classified as
`unknown` — and hung again on the repair call, this time with the socket sitting in
`ESTABLISHED` rather than `CLOSE_WAIT`, but otherwise identical: 10+ minutes of zero CPU
progress on the same unclosed connection, well past `GroqModelClient`'s own `timeout=120`
+ 3 retries (docs/decisions.md D49), which should have raised an error either way. Two
different socket states across two attempts both failing to resolve within the client's
stated timeout points at an infrastructure-level problem — either something about this
specific request (payload size/shape for this repo) that the Groq API or an intermediate
proxy handles by holding the connection open indefinitely instead of responding or
closing, or a local networking/sandbox condition that prevents `requests`' own read
timeout from firing — rather than a fluke in one run. The harness's `wallclock_cap_s=900`
budget check (`agent/budget.py`) is evaluated between graph nodes, not as a hard interrupt
on a blocking call, so it can't rescue a call that never returns either way. Both attempts
were killed manually. **This cell is an infrastructure gap, not a zero** — treat
`okfn__opendataeditor`'s OFF-arm score as unmeasured, and treat the hang itself as a
finding: repair calls against this repo (at least) can stall past the client's own
declared timeout, independent of `use_triage`, which is worth root-causing before trusting
any Groq-backed run's silence to mean "no requests are stuck."

## Preliminary per-class attempt tally (`use_triage=True` arm, all 7 repos)

Same caveat as before: this is a hand-reconstruction from structlog events with a small
sample size — read it as "what happened in these attempts," not a rate.

| Class | Attempts | Outcome |
|---|---|---|
| `unknown` | 10 | 1 fixed (`kor`'s `parser.py`, +40 tests passing); 7 not fixed (`pydantic-argparse`'s hard case); 1 applied with inconclusive effect (`rohmu`'s `statsd.py`, next repair attempt hit `413` before an isolated re-test could attribute a delta); 1 failed outright (`opendataeditor`, `413` before a class could even be pinned down) |
| `class_def_error` | 2 | 1 fixed (`rohmu`, 0/195 → 170/195 in one call); 1 discarded (`draco2` — model named a file never shown to it, rejected by the I1-I3 guard, not a fix) |
| `validation_behaviour` | 2 | 1 fixed (`madkote`'s `logger.py`, the D50-verified repair); 1 applied with inconclusive effect (`rohmu`'s `config.py`, second pass — narrow re-test didn't cover a node_id this specific edit could have changed) |
| `import_error` | 1 | Not fixed (`pydantic-argparse`) |

## What's NOT here yet

- **`okfn__opendataeditor`'s `use_triage=False` score.** Unmeasured, not zero — hung on
  two separate attempts (the full corpus run and an isolated targeted rerun), both killed
  manually. This is now a suspected infrastructure issue (a `requests` call that outlives
  its own `timeout=120` with no exception raised) rather than a one-off, and it should be
  root-caused — e.g. reproduce outside the harness with a bare `requests.post` against the
  same payload, check for a network proxy in the sandbox environment that silently holds
  connections open — before trusting this pipeline's silence elsewhere to mean "nothing is
  stuck."
- **Classifier accuracy on a hand-labelled set.** `docs/results/triage_failures_dev.jsonl`
  has real residual failures with predicted classes and full traceback text, but nothing
  has been hand-labelled against it yet, and it's overwritten each run rather than
  accumulated.
- **A full, statistically meaningful per-class fix-success table.** Needs both a bigger
  corpus (7 repos still gives too few samples per class) and the `AgentState`
  repair-attempt-history extension flagged in D40 — right now this is reconstructed by
  hand from structlog events, which doesn't scale and can't attribute inconclusive cases
  cleanly (see `rohmu`'s two entries above).
- **Multiple seeds/reruns for variance.** One run per arm. `rohmu`'s ON/OFF gap moved
  slightly between this run and the previous one (0.87/0.86 → 0.89/0.86) purely from which
  iteration happened to hit the `413` limit — a reminder that single-run deltas on this
  corpus size can shift run to run even with no code changes.
- **The `413 Payload Too Large` limitation itself.** It hit three separate repos this run
  (`rohmu` ON, `rohmu` OFF, `draco2` OFF, `opendataeditor` OFF) and is now the single most
  common reason a repair attempt fails outright, ahead of any genuine model mistake. Worth
  addressing directly (e.g. truncating/summarizing large failure batches) before drawing
  further conclusions from repos that hit it.

## Raw data

- Full run logs with every `agent.*` event: session-local, not retained past this run —
  this writeup was reconstructed from the live log tail during monitoring, since the
  script's own `corpus_run_groq_results.json` was never written for this run (it's written
  once at full completion, which didn't happen because the `opendataeditor` OFF cell was
  killed mid-run).
- Residual failures with full text: `docs/results/triage_failures_dev.jsonl`
