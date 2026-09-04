# Pydantic Migration Agent — Master Build Plan

An autonomous agent that migrates Python repositories from Pydantic v1 to v2:
plans, edits source, runs the test suite in a sandbox, triages failures, retries,
and opens a pull request with a rationale and a confidence score.

**Status:** planning complete, nothing built.
**Owner:** Arnav.
**Working agreement:** see [CLAUDE.md](CLAUDE.md). Claude scaffolds and reviews; you implement and must be able to defend every decision.

---

## 0. The one-sentence thesis

> Migration is a graph problem with a verifier attached: the dependency graph tells you
> *what* to change and in *what order*, the test suite tells you whether you were right,
> and the failure log tells you what to do next. Everything else is plumbing.

Every architectural decision below traces back to that sentence. If you can't trace it, cut it.

---

## 1. What "done" means

Three artefacts, in priority order:

1. **A number.** Test-suite pass rate across a held-out corpus of real repos, with an
   honest denominator and a confidence interval.
2. **An ablation.** Graph retrieval vs. embedding retrieval, same everything else.
   The number in (1) is only interesting because (2) proves the architecture caused it.
3. **A failure analysis.** A table of failure classes and how often each was fixed.
   This is what you talk about for 15 minutes in an interview.

The PR workflow, dashboard, and MCP server are *credibility* — they matter only after 1–3 exist.

---

## 2. Non-negotiable invariants

These are the rules that keep the number honest. Violating any one of them makes the
whole project unpublishable, so they are enforced mechanically, not by discipline.

| # | Invariant | Enforced by |
|---|---|---|
| I1 | The agent may never edit test files. | Path allowlist in the patch applier; run aborts on violation. |
| I2 | The agent may never delete, skip, xfail, or weaken a test. | AST diff check on test files (should be no-ops) + grep for `skip`/`xfail` additions anywhere. |
| I3 | The agent may never pin pydantic back to `<2`. | Dependency-file check post-run; the sandbox installs pydantic v2 regardless of what the repo asks for. |
| I4 | Only tests that passed on the pre-migration baseline count toward the score. | Baseline test set recorded in Phase 0, stored in the corpus manifest. |
| I5 | Prompt/model changes are evaluated on the dev split; the test split is run at most 3 times total. | Split recorded in the manifest; eval harness refuses `--split test` without `--i-know-what-im-doing`. |
| I6 | Every scored run is reproducible from its trace: model id, prompt hash, corpus sha, seed, temperature 0. | Run manifest written by the eval harness. |
| I7 | No PR is ever opened against a repo you do not own. Push to your own forks. | Hardcoded org allowlist in the PR module. |

I4 and I5 are the ones students skip and interviewers catch.

---

## 3. Architecture

```
                       ┌───────────────────────────────────────┐
                       │            eval/ (Phase 5)            │
                       │  corpus × configs → metrics + tables  │
                       └───────────────┬───────────────────────┘
                                       │ drives
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                          agent/ — LangGraph loop (Phase 3)                   │
│                                                                              │
│   plan ──▶ select_unit ──▶ edit ──▶ validate ──▶ run_tests ──▶ triage ──┐    │
│     ▲                                                                   │    │
│     └───────────────────────── repair ◀─────────────────────────────────┘    │
└───┬──────────────┬─────────────────┬──────────────────┬─────────────────┬────┘
    │              │                 │                  │                 │
┌───▼────┐  ┌──────▼──────┐  ┌───────▼──────┐  ┌────────▼──────┐  ┌───────▼─────┐
│ graph/ │  │  codemod/   │  │   sandbox/   │  │   triage/     │  │   trace/    │
│ Ph. 1  │  │  Ph. 3      │  │   Ph. 2      │  │   Ph. 4       │  │   Ph. 6     │
│tree-   │  │deterministic│  │Docker, no    │  │classify       │  │JSONL +      │
│sitter  │  │AST rewrites │  │network, caps,│  │failures,      │  │SQLite,      │
│→ Neo4j │  │for the      │  │structured    │  │route to fix   │  │replayable   │
│        │  │mechanical   │  │pytest report │  │strategy       │  │             │
│        │  │80%          │  │              │  │               │  │             │
└────────┘  └─────────────┘  └──────────────┘  └───────────────┘  └─────────────┘
                                       │
                              ┌────────▼────────┐   ┌──────────────┐
                              │ guardrails/ Ph.7│   │ pr/ Phase 6  │
                              │ injection defs, │   │ fork, branch,│
                              │ sandbox harden  │   │ draft PR     │
                              └─────────────────┘   └──────────────┘
```

### Why each component exists (one line you must be able to say out loud)

- **graph/** — "You must migrate a module before anything that imports it; that's a topological sort over the import graph. Embeddings can't give you an ordering."
- **codemod/** — "Roughly 80% of a Pydantic v1→v2 diff is mechanical and deterministic. Spending frontier-model tokens on `.dict()` → `.model_dump()` is a waste of money and a source of variance. The model's budget belongs on the semantic 20%."
- **sandbox/** — "The agent executes model-written code against arbitrary GitHub repos. That's a live security boundary, and it's also the only source of ground truth in the system."
- **triage/** — "A 4000-line pytest log is not a prompt. Classifying the failure and routing it to a targeted strategy is the engineering the model can't do for me."
- **trace/** — "Every number I report has to be reconstructible from a trace, or it isn't a number."
- **guardrails/** — "The repo I'm migrating contains comments and docstrings the model reads. That is an untrusted input channel."

### Deliberately not built

Multi-agent orchestration. If the loop needs a planner/editor/verifier split it will emerge
from the state machine. Adding agents for the word "multi-agent" is a negative signal now.

---

## 4. The hybrid edit strategy (the most important design decision)

Do **not** build an LLM-only agent. Build three tiers and measure each:

| Tier | Mechanism | Handles | Cost |
|---|---|---|---|
| T1 | Deterministic AST codemods (`codemod/`) | Renames and mechanical rewrites: `.dict()`, `.json()`, `parse_obj`, `@validator`, `class Config`, `orm_mode`, `regex=`, `__fields__`, `update_forward_refs`, `BaseSettings` import move | ~$0 |
| T2 | LLM edit with graph-retrieved context, triage-routed prompt | Semantic changes: implicit-Optional defaults, coercion strictness, custom validators, `__get_validators__` → `__get_pydantic_core_schema__`, `json_encoders`, error-message assertions | $$ |
| T3 | LLM repair loop on residual test failures | Whatever T1+T2 got wrong | $$$ |

This gives you a **third ablation for free**: T1-only vs T1+T2 vs T2-only (no codemods).
If T1-only already scores 40%, that is a genuinely interesting and honest result, and it
tells you exactly where the model is earning its keep.

There is an official `bump-pydantic` codemod tool. **Write your own T1 anyway** — it's a
weekend, it's LibCST/AST work you can defend, and depending on someone else's codemod
means you can't explain your own diff. Read theirs for a rule list; don't import it.
(If time collapses, using it is a legitimate fallback — just say so in the README.)

---

## 5. Phase plan

Phases 1–5 are the project. 6–7 are credibility. 8 is optional.

| Phase | Deliverable | Done when | Est. |
|---|---|---|---|
| 0 | Corpus + infra | 30–40 repos with green pre-migration baselines, reproducible, split dev/test | 1.5 wk |
| 1 | Code graph + retrieval | Given a symbol, returns true dependents/dependencies + topo order from Neo4j | 2 wk |
| 2 | Sandbox + test runner | Any corpus repo builds and runs its suite isolated; structured results | 1 wk |
| 3 | Migration loop (T1+T2+T3) | End-to-end green on **one** repo, fully traced | 2 wk |
| 4 | Failure triage | Failures classified and routed; measured pass-rate lift vs Phase 3 | 1.5 wk |
| 5 | Eval harness + ablations | Full corpus scored; ablation + multi-model tables produced | 1.5 wk |
| 6 | Trace + PR workflow | Every run replayable; agent opens a real draft PR on your fork | 1 wk |
| 7 | Guardrails | Sandbox hardened; injection red-team corpus with a measured resistance number | 1 wk |
| 8+ | Optional | Semgrep gate (2d) · MCP server (2d) · LoRA distillation (1 wk) | — |

**~11 weeks part-time to end of Phase 7.** Phase 0 is the one people underestimate by 3×.

Detailed spec per phase: [docs/phase-0-corpus.md](docs/phase-0-corpus.md) … [docs/phase-7-guardrails.md](docs/phase-7-guardrails.md).
Cross-module contracts: [docs/interfaces.md](docs/interfaces.md).
Decision log with interview answers: [docs/decisions.md](docs/decisions.md).

---

## 6. Repository layout

```
project_creation/
├── PLAN.md                     # this file
├── CLAUDE.md                   # working agreement + conventions
├── README.md                   # written LAST, and it does more work than the code
├── pyproject.toml
├── docs/
│   ├── interfaces.md
│   ├── decisions.md            # ADR log
│   ├── phase-0-corpus.md … phase-7-guardrails.md
│   └── results/                # generated tables, committed
├── corpus/
│   ├── manifest.json           # the corpus, versioned, hand-curated
│   └── scripts/                # discovery, validation, baseline capture
├── src/pmigrate/
│   ├── graph/                  # Phase 1: tree-sitter → Neo4j
│   │   ├── ir.py                # parser's intermediate representation
│   │   ├── parser.py           # tree-sitter → IR
│   │   ├── resolver.py         # import resolution (the hard part)
│   │   ├── toposort.py         # Tarjan SCC + condensation order — pure, backend-independent
│   │   ├── relevance.py        # which symbols touch pydantic → the work list
│   │   ├── protocol.py         # the CodeGraph contract both backends implement
│   │   ├── build.py             # pure SymbolRef/edge construction, shared by both backends
│   │   ├── repo_files.py       # shared file-reading for ingest()
│   │   ├── token_budget.py     # shared neighbourhood() truncation heuristic
│   │   ├── memory_store.py     # in-memory CodeGraph — tested end-to-end (see decisions.md D2/D11)
│   │   ├── store.py            # Neo4j CodeGraph — real Cypher, UNVERIFIED (no live Neo4j here)
│   │   └── queries.py          # Cypher query text used by store.py
│   ├── sandbox/                # Phase 2
│   │   ├── protocol.py         # the Sandbox contract
│   │   ├── policy.py           # docker CLI args: network, resource caps, overlay mounts — tested
│   │   ├── image.py            # build + cache docker images per repo@commit — verified against a live daemon
│   │   ├── results.py          # pytest-json-report -> TestRun — tested against real captured JSON
│   │   └── runner.py           # DockerSandbox — verified against a live daemon (see decisions.md D13/D14)
│   ├── codemod/                # Phase 3 T1 — 15 LibCST rules, all tested, kitchen-sink integration test
│   │   ├── protocol.py         # CodemodRule contract, RuleEdit
│   │   ├── engine.py           # apply_rules(source, path, rules) — per-rule exception isolation (D22)
│   │   └── rules/               # one file per rule + shared factories in _common.py
│   ├── agent/                  # Phase 3 — state machine wired, tested, and run against real Docker + real corpus
│   │   ├── state.py            # AgentState, Edit
│   │   ├── budget.py           # BudgetState + NoProgressDetector — tested
│   │   ├── diff.py             # unified diff parse/generate — tested
│   │   ├── patch.py            # apply_patch: the I1-I3 invariant chokepoint — tested
│   │   ├── model_client.py     # ModelClient protocol + FakeModelClient (no API key here to verify a real one)
│   │   └── graph.py            # LangGraph loop — T1-only verified on madkote/fastapi-plugins: 22/23
│   │                           #   passing, zero LLM calls (D16-D20); structlog trace events per PLAN.md §7
│   ├── triage/                 # Phase 4 — rules+grouping+classifier built and tested (D36);
│   │                           #   FailureClass/Diagnosis live in types.py, not here
│   │   ├── protocol.py         # Classifier Protocol
│   │   ├── collect.py          # TestRun -> per-node-id RawFailure, shared with agent/repair.py
│   │   ├── rules.py            # regex classification — only classes with real corpus evidence
│   │   ├── grouping.py         # PREEXISTING via baseline, then group by (class, root frame);
│   │                           #   group_raw_failures() -> GroupedDiagnosis (Diagnosis + full
│   │                           #   RawFailures), classify_and_group() a thin wrapper over it (D38)
│   │   └── classifier.py       # RuleBasedClassifier — no LLM fallback yet, no real UNKNOWNs
│   │                           #   labelled to build/verify one against. Wired into
│   │                           #   agent/graph.py (D37): a `classify` node populates
│   │                           #   AgentState.diagnoses; route() skips repair() when every
│   │                           #   diagnosis is PREEXISTING — verified live against iscc-core
│   │                           #   to skip a real would-have-cost-money T2 attempt. repair()'s
│   │                           #   own target-selection now routes through Diagnosis too (D38):
│   │                           #   picks one GroupedDiagnosis by priority (mechanical fixes
│   │                           #   before semantic ones), prompts on just that diagnosis's text.
│   ├── trace/                  # Phase 6
│   ├── pr/                     # Phase 6
│   ├── guardrails/             # Phase 7
│   └── eval/                   # Phase 5 — minimal slice pulled forward into Phase 4 (D40):
│       │                       #   phase-4-triage.md's own acceptance criteria (accuracy,
│       │                       #   pass-rate lift, cost, fix-rate table) need a harness to
│       │                       #   exist at all. No EvalConfig/retrieval/tiers/seed/
│       │                       #   resumability yet — those wait for Phase 5 real evidence.
│       ├── harness.py          # run_repo/run_corpus/checkout_pre_sha; also dumps real
│       │                       #   failure text + predicted class to JSONL for hand-labelling
│       └── metrics.py          # RepoScore + score_run() — pass_rate/full_green/iterations/
│                               #   usd_spent/wallclock_s/final_diagnosis_counts; no diff
│                               #   similarity or symbol precision/recall yet (Phase 5)
└── tests/                      # YOUR tests, mirroring src/
```

---

## 7. Metrics — log from Phase 3, never retroactively

Written to `docs/results/` as generated markdown tables.

**Primary**
1. Pass rate, zero human edits (baseline-adjusted per I4)
2. Pass rate with one human review pass
3. Diff similarity to the human migration — report **two** measures:
   - line-level Jaccard over changed lines (whitespace-normalized)
   - **symbol-level precision/recall**: of the symbols the human changed, what fraction did the agent change, and vice versa (computed from the Phase 1 graph — a nice reuse)

**Ablations** (same corpus, same model, same seed, one variable)
4. Retrieval: graph vs. embedding vs. whole-file-dump
5. Edit tier: T1-only vs T1+T2+T3 vs T2+T3-only
6. Triage: on vs off (this is the Phase 4 acceptance criterion)

**Operational**
7. Median and p95 cost per repo (USD)
8. p95 wall-clock latency per repo
9. Failure-class distribution and per-class fix rate ← *the interview table*
10. Iterations-to-green distribution
11. Injection resistance rate (Phase 7)

**Honesty rules.** N≈34 means wide intervals. Report bootstrap 95% CIs, publish the
per-repo table, run k=3 seeds on the dev split to show variance, and state the model
version and date. "48% with a good failure analysis" beats "90%" nobody believes.

### Current measured results (2026-09-04)

`docs/results/main.md` — the cross-arm bootstrap-CI table D65's `write_main_report`
produces — now has real numbers behind it for the first time: all 7 arms (`embedding`,
`graph`, `wholefile`, `t1_only`, `no_t1`, `no_triage`, `model_groq`) scored against the
same 7-repo dev-split corpus slice, each genuinely re-attempted this date (stale resume
caches cleared first, not replayed).

**Headline: 0/7 repos reached `full_green` on any arm this round.** Every arm lands at
the identical 0.266 mean pass rate — T1's mechanical rewrites are doing all the currently
visible work; no retrieval strategy, tier combination, triage setting, or model swap has
yet flipped a single currently-failing test to passing on this corpus slice. This is an
honest, not a manufactured, flat result (D65's own reasoning: report the interval, don't
hide it) — see §1's own thesis that the number matters more than the story.

Real signal did come through despite the flat headline:
- `graph` got genuine T2/T3 repair attempts past Gemini's quota wall this time: real
  cost ($0.04 mean/repo), a consistently unparseable-patch failure mode on
  `iscc__iscc-core` (`corrupt patch at line 392`, twice, not a one-off), and two
  mechanically-accepted repairs that didn't change `pass_rate`.
- `model_groq` reproduces that same "repair applies cleanly, doesn't fix the test"
  pattern independently, on a different provider — the same two repos, the same zero
  effect, on both this run and the original one.
- `wholefile`/`no_t1`/`no_triage` are still substantially quota-blocked (Gemini's
  free-tier 429 wall, D48) — genuinely re-attempted, not left stale, but the daily quota
  window hasn't stayed open long enough to get a real T2/T3 measurement through for most
  of them.

**What this means for the plan:** §1's "an ablation" deliverable doesn't exist yet in a
meaningful form — graph-vs-embedding-vs-wholefile can't be honestly compared on evidence
this thin and this quota-starved. §10's resume bullet stays a placeholder; there's no
positive result yet to replace it with honestly. The real blocker right now isn't the
architecture, it's Gemini's free-tier quota — worth a deliberate decision on paying for
quota, switching the primary model, or accepting a much smaller N of real T2/T3 attempts
as the ceiling. Separately: `main.md` technically now satisfies "real measured numbers,"
the CLAUDE.md condition that unlocks Phases 6+ — but the result itself is degenerate
(0/7 full green, still quota-limited), so treat that gate as not meaningfully cleared
yet, not as a green light to start Phase 6.

Full per-repo tables and CIs: `docs/results/main.md`. Per-arm caveats and live-run
narrative: `docs/results/*.md`. The `embedding` arm's crash under `max_workers>1`
(concurrent `SentenceTransformer` construction with no lock) was found and fixed this
session — see D67 in `docs/decisions.md`.

---

## 8. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Phase 0 yields <15 usable repos | **High** | Start discovery week 1 and run it in the background throughout. Relax filters: accept repos where only a subset of the suite is green. Fallback: synthesize a corpus by *reverting* v2 repos to v1 patterns with your own codemods (state this clearly in the README if used). |
| Docker/env hell — old repos won't install | High | Pin a base image per Python minor; allow a per-repo `setup_overrides` field in the manifest; cap install debugging at 30 min/repo, then drop the repo and record why. Track the drop reasons — that list is itself a good README section. |
| Cost blowout | Medium | Hard budget guard in `agent/budget.py`: per-repo USD cap, global cap, kill on breach. Prompt caching on repo context. Cheap model for T1-adjacent classes. Log every call. |
| Agent "cheats" to green | Medium | Invariants I1–I3, enforced mechanically. Also spot-check 5 diffs by hand every eval run. |
| Neo4j is overkill and slows you down | Medium | Build `graph/` against an interface (see interfaces.md). If Neo4j becomes friction, the in-memory networkx backend is a 1-day swap and the interfaces don't change. Keep Neo4j as the primary because the traversal queries and the persistent store are real, but don't let it block Phase 3. |
| Scope creep into Phase 8 before 5 is done | Medium | Phases 6–8 are locked until `docs/results/main.md` has real numbers in it. |
| Overfitting prompts to the corpus | Medium | Invariant I5: dev/test split, test split run ≤3 times. |

---

## 9. Prerequisites to install before Phase 0

- **Docker Desktop — not currently installed on this machine.** Blocker for Phase 2; install it during Phase 0.
- Neo4j — run via Docker (`neo4j:5-community`), not a local install.
- Python 3.11 for the *agent* (3.13 may fight some deps); repos under test get their own images.
- A GitHub personal access token with `public_repo` (search + fork + PR).
- Anthropic + OpenAI API keys; Ollama for the local-model arm.

---

## 10. Target resume bullet (numbers are placeholders — replace with measurements)

> Built an autonomous codebase migration agent (Python, tree-sitter, Neo4j, Docker,
> LangGraph, GitHub API). Migrated 34 open-source repos from Pydantic v1→v2: 71% reached
> full test-suite pass with zero human edits, 89% with one review pass. Graph-based
> retrieval over the AST beat embedding retrieval by 24 points on pass rate. Sandboxed
> execution with prompt-injection defences; full audit trace and cost accounting at
> $0.41 median per repo.
