# Decision log

Every entry: the decision, the alternative rejected, the reason, and **the sentence you say
in an interview**. If you can't fill in the last field, the decision isn't made yet.

Add to this file whenever you make a load-bearing choice. It is the source material for the
"walk me through a hard decision" part of an interview, which is 15 of your 20 minutes.

---

## D1 — Pydantic v1→v2 as the migration target

**Alternatives:** SQLAlchemy 1.x→2.0 · Python 2→3 · unittest→pytest · a generic
"any migration" agent.

**Why:** ground truth is free. Hundreds of repos have done this migration publicly, so for
every task you have the human's answer sitting in git. That converts a demo into an
evaluation with two metrics (test pass rate *and* similarity to the human diff) instead of
one. Secondary: breaking changes are exhaustively documented, blast radius per repo is
small enough to be tractable, and demand is still live.

**Interview:** "I picked it because the migration has already been done publicly hundreds of
times, which means every task in my corpus comes with the human's answer attached. That's
what let me build a real evaluation instead of a demo."

---

## D2 — Neo4j for the code graph

**Alternatives:** networkx in memory · SQLite with recursive CTEs · a vector store only.

**Why:** the queries are variable-length graph traversals ("everything that transitively
imports this, up to depth 3, along these edge kinds"), which Cypher expresses directly and
recursive SQL expresses painfully. It's also a persistent store, so graph construction is
decoupled from the agent process — you ingest once and every eval arm queries the same graph.

**Honest caveat you should volunteer:** for a single repo, networkx would be enough, and
the code is written against a `CodeGraph` protocol precisely so the backend is swappable.
Neo4j earns its place at corpus scale and because the query language is the right level of
abstraction, not because graphs-are-cool.

**Interview:** "Cypher expresses transitive dependency traversal directly, and I needed a
persistent store so ingest was decoupled from the agent. I also wrote it behind a protocol —
for one repo networkx would do, and I want to be honest that Neo4j is earning its keep at
corpus scale rather than being load-bearing for correctness."

---

## D3 — Graph retrieval over embedding retrieval

**Alternative:** embed code chunks, retrieve by cosine similarity (the default RAG move).

**Why:** what matters for a migration is which symbols *call* which, not which files *sound*
similar. And the graph gives an **ordering** — you must migrate a module before its
dependents, which is a topological sort. Similarity scores cannot express that.

**Backed by measurement, not assertion:** this is ablation arm `embedding` in Phase 5, run
with everything else identical. If the gap is small, the honest thing is to report the small
gap.

**Interview:** "Embeddings retrieve what sounds similar; migration needs what's connected,
and it needs an order. I ran both arms with everything else held constant and measured the
difference rather than assuming it."

---

## D4 — Hybrid edit strategy: deterministic codemods before the LLM

**Alternative:** LLM-only agent (the obvious build) · codemod-only (the `bump-pydantic`
approach).

**Why:** ~80% of a Pydantic v1→v2 diff is mechanical renaming. Spending frontier-model
tokens on `.dict()` → `.model_dump()` is expensive, slow, and adds sampling variance to a
transformation that has exactly one right answer. Codemods handle those deterministically
and for free; the model's budget goes to the semantic 20% — implicit-Optional defaults,
coercion strictness, custom validator protocols — where it's actually needed.

It also gives you a free third ablation (T1-only vs. hybrid vs. LLM-only), which tells you
precisely where the model earns its cost.

**Interview:** "Most of this migration is deterministic, so I wrote codemods for it and spent
the model on the parts that need judgment. Then I measured all three configurations — the
codemods alone get you a long way, and knowing exactly how far is the interesting part."

---

## D5 — Rule-first triage, LLM only as fallback

**Alternative:** dump the pytest log into the context and let the model figure it out.

**Why:** a 4000-line log buries the signal and costs a fortune. Classification by regex and
traceback parsing is deterministic, testable, nearly free, and — the key part — lets each
failure class carry its own **allowed edit surface**. A third-party version conflict gets a
strategy that can only touch dependency files, so the model can't "fix" it by rewriting
models.

**Interview:** "A dependency conflict and a coercion-semantics change are completely
different problems that both look like a red test. Classifying them lets me constrain what
the model is even allowed to edit for each one."

---

## D6 — Only baseline-passing tests count (invariant I4)

**Alternative:** score against the full suite.

**Why:** real repos have tests that were already failing before the migration. Counting
those makes your pass rate look worse than reality — or, if you're careless about which
direction, lets a repo look green because its suite never ran. Capturing the exact set of
tests that passed pre-migration and scoring only against that set is the only honest
denominator.

**Interview:** "I recorded which tests passed *before* the migration and scored only against
that set. Otherwise I'd be crediting or blaming the agent for failures that had nothing to
do with it."

---

## D7 — dev/test corpus split, test split run at most three times (invariant I5)

**Alternative:** iterate on all 34 repos.

**Why:** prompt engineering against your whole corpus is overfitting with extra steps. You
will absolutely convince yourself a prompt tweak is a real improvement when it's noise on
twelve repos. A held-out split you barely touch is the only way the final number means
anything.

**Interview:** "I split the corpus and only ran the held-out half at the very end. Every
prompt change I made was scored on the dev half — otherwise the final number is just
memorised."

---

## D8 — No multi-agent orchestration

**Alternative:** planner / editor / verifier as separate agents.

**Why:** the split would be cosmetic. The loop is already a state machine with distinct
nodes; wrapping each node in its own agent adds coordination overhead, more failure modes,
and more cost for no measured gain. If the problem demands the split later, the state
machine already has the seams. "Multi-agent" as a feature claim is increasingly a negative
signal.

**Interview:** "I have a planner, an editor, and a verifier — they're nodes in a state
machine, not separate agents. The split exists where it earns something; I didn't add
coordination overhead to be able to use the word."

---

## D9 — Fork before opening PRs (invariant I7)

**Alternative:** open PRs directly against the upstream repos.

**Why:** unsolicited AI-generated PRs against real maintained projects waste maintainers'
time and are a bad look on a portfolio. The workflow is identical against a fork, so there's
no demonstration value lost.

**Interview:** "The PR workflow runs against my own forks. Opening machine-generated PRs on
projects I don't maintain would be discourteous, and it doesn't prove anything the fork
doesn't."

---

## D10 — Tool-layer enforcement over prompt-based rules

**Alternative:** instruct the model not to edit tests, not to skip, not to downgrade pydantic.

**Why:** a prompt is a suggestion; `apply_patch` is a chokepoint. Every write goes through
one function, and that function enforces I1–I3 mechanically. This is also the real
prompt-injection defence: no instruction planted in a repo's docstrings can grant a
capability the tool layer doesn't allow. Detection is defence in depth, not the mechanism.

**Interview:** "All the invariants are enforced in the single function that applies patches,
not in the prompt. That's also why prompt injection through repo comments can't do much —
it can influence what the model *wants* to do, but not what the tool layer permits."

---

## Template

```
## D<n> — <decision>
**Alternatives:**
**Why:**
**Interview:**
```
