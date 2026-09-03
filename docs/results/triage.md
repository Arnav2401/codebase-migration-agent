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
stated timeout looked at the time like an infrastructure-level problem outside this
project's code. **Root-caused since** (docs/decisions.md D53): it wasn't infrastructure at
all. `GroqModelClient._post_with_retry` (D49) slept for Groq's `Retry-After` header value
**uncapped** and logged nothing before sleeping — a large header value on a transient 429
produces exactly this signature (a live process, near-zero CPU, a stale socket) with no
way to tell it apart from a real network stall from the outside. Confirmed live: the SAME
signature recurred on `Aiven-Open__rohmu` (a different repo entirely) on a later run, with
a THIRD different socket state (`CLOSED`) — three sightings, three socket states, one
underlying cause. D53 caps the sleep at 30s and logs before sleeping, so this specific
failure mode shouldn't recur in future runs, but it was still real and unresolved for
*this* run's data. **This cell remains an infrastructure-adjacent gap, not a zero** —
treat `okfn__opendataeditor`'s OFF-arm score as unmeasured for this writeup; a rerun after
D53 would be expected to complete normally.

## Per-class fix-success table (D51/D52's real join, not a hand reconstruction)

**This table is from a DIFFERENT run than the headline comparison above** — a full
7-repo `use_triage=True` pass against `GeminiModelClient` (`gemini-3.6-flash`), run to
validate D54's Gemini retry fix, not the Groq run the rest of this doc covers. Called out
explicitly so the two aren't mistaken for the same experiment: `docs/phase-4-triage.md`'s
"same model, same seed" requirement means this table cannot be paired with the Groq-backed
OFF-arm numbers above for an ON-vs-OFF claim — Gemini's own OFF arm hit a hard quota wall
immediately on every repo (0 real attempts, all `429`), so there is no same-model OFF data
to compare against yet. What this table DOES give, for the first time: `eval/metrics.py`'s
`fix_success_table` (D52) computed automatically from real `AgentState.repair_attempts`
history (D51), not reconstructed by hand from log lines.

| Class | Attempts | Applied | Fixed | Fix rate |
|---|---|---|---|---|
| `unknown` | 14 | 11 | 6 | **0.55** |
| `class_def_error` | 2 | 2 | 0 | 0.00 |
| `validation_behaviour` | 1 | 1 | 0 | 0.00 |

`unknown`'s 0.55 fix rate is the first per-class number in this project with a sample
size (14 attempts) large enough to mean anything at all. The two 0.00 rows are NOT
evidence those strategies don't work — they're D52's own stated limitation showing up
for real: `rohmu`'s `class_def_error` repair visibly took it from 0/195 to 173/195 passing
in this same run (confirmed in the raw log), but that diagnosis originated from a
collection error, which has no individual test node_id to check — `fixed` requires
`node_ids` to be non-empty by construction (docs/decisions.md D52), so a collection-error
diagnosis can never register as "fixed" even when it obviously worked. Read `applied=2,
fixed=0` here as "this class isn't currently measurable by this join," not "this class
fails."

## Classifier accuracy: 96.8% (D55/D56)

`docs/phase-4-triage.md`'s last unmeasured acceptance criterion: ≥85% on ≥100
hand-labelled real failures. All 411 raw failures in `triage_failures_dev.jsonl` are now
labelled (`tests/fixtures/triage/labelled_dev.jsonl`, via `pmigrate triage label`'s
group-based hand-labelling session — D55) and continuously checked by
`tests/eval/test_classifier_regression.py`, which re-classifies every entry fresh through
the real `RuleBasedClassifier` (not a stale stored prediction) and asserts ≥0.85.

The path here is worth reading, not just the final number: the raw pass was 72.5%, a real
fail. Investigating before accepting that number found 20 of the "misses" were the
*labelling* tool's fault, not the classifier's — `PREEXISTING` depends on baseline
membership the tool never showed a human labeller, and one group-based shortcut (D55's own
stated risk) genuinely merged two unrelated failures under one label. Corrected, that left
76.9% and three clean, evidenced gaps — `.model_copy()`/`.model_dump()` on a non-model
value (the single biggest miss, 45 failures), two more class-definition-time exception
shapes, and one overly-narrow `ImportError` pattern. Four new rules in `triage/rules.py`
later: **96.8%** (398/411), with two known, accepted residual gaps documented in D56
rather than chased with overfit regexes. Full trace: docs/decisions.md D56.

## What's NOT here yet

- **`okfn__opendataeditor`'s `use_triage=False` score.** Unmeasured, not zero — hung on
  two separate attempts (the full corpus run and an isolated targeted rerun), both killed
  manually. Root-caused since (D53: an uncapped `Retry-After` sleep in
  `GroqModelClient._post_with_retry`, now fixed) — a rerun should complete normally, just
  hasn't been done yet for this writeup.
- **A same-model fix-success table.** The real, automated table above (D51/D52) exists
  now, but only for a `use_triage=True`-only Gemini run — Groq's own equivalent needs a
  clean run once its daily token quota resets, and Gemini's own OFF arm needs its quota
  to reset too before a same-model ON/OFF fix-success comparison is possible.
- **A fix-success join that handles collection-error diagnoses.** `class_def_error` and
  any other diagnosis whose only frame is a collection error has `node_ids=()` and can
  never register as "fixed" by the current join, even when the repair visibly worked (see
  `rohmu` above). Worth extending — e.g. falling back to "did overall pass count increase"
  for empty-node_ids attempts — once there's a concrete case where it matters for a
  real conclusion, not preemptively.
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
- Hand-labelled ground truth (411 real failures, D55/D56): `tests/fixtures/triage/labelled_dev.jsonl`
- Gemini fix-success-table run (scratch, not committed): `corpus_run_gemini_results.json`
  via `scratchpad/run_corpus_gemini.py` — the same run also confirmed D48's original
  Gemini free-tier finding live a second time: `use_triage=True` got 6 of 7 repos through
  with real repair attempts (~15-18 real model calls) before hitting a hard `429` on the
  7th, after which every remaining repo/arm cell failed immediately with zero spend —
  consistent with the ~20-requests/day cap D48 first observed.
