# Phase 1 — Code graph and retrieval

**Est. 2 weeks. This is the component that distinguishes the project. Do it properly.**

## Why this exists

Naive embedding search over code chunks retrieves files that *sound* similar. Migration
needs files that are *connected*: what imports this, what subclasses this, what breaks if
this signature changes. And it needs an **order** — you must migrate a module before the
modules that import it. Embeddings cannot express an ordering; a topological sort over the
import graph can.

> Interview answer, verbatim: "You must migrate a module before anything that imports it,
> and that's a topological sort over the dependency graph. That's not something a similarity
> score can give you."

## Deliverable

`CodeGraph` (interfaces.md §2) implemented over Neo4j, plus `work_list()` — the
topologically-ordered set of pydantic-touching migration units that *is* the agent's plan.

## Build order

### 1.1 Parser (`graph/parser.py`)

tree-sitter-python → a language-agnostic IR. Extract per file:

- module docstring, imports (`import x`, `from x import y as z`, relative `from ..a import b`)
- class defs: name, bases, decorators, body symbols, line range
- function/method defs: name, params, decorators, return annotation, line range
- module-level assignments (config objects, type aliases)
- call sites and attribute accesses (`obj.dict()`, `Model.parse_obj(...)`)

Use tree-sitter for structure — it's fast and error-tolerant on files that don't parse.
Use `ast`/LibCST when you need real semantics (and for codemods in Phase 3). Both is fine;
say why: tree-sitter for the whole-repo sweep, LibCST for the precise rewrite.

### 1.2 Resolver (`graph/resolver.py`) — the hard part

Turn import statements into edges between actual modules. You must handle:

- relative imports (`from . import x`, `from ..pkg.mod import y`) → absolute module path
- `src/` layouts, namespace packages, `__init__.py` re-exports (a symbol's definition site
  differs from its import site — `from app.models import User` where `models/__init__.py`
  does `from .user import User`)
- aliasing (`import numpy as np`), star imports (record as a module-level edge, flag it)
- conditional/`TYPE_CHECKING` imports (keep, mark `type_only=True`)
- third-party vs. first-party (only first-party gets full nodes; third-party gets a stub
  node so you can still answer "does anything import `pydantic.BaseSettings`?")

**This is where correctness is won or lost.** Write it test-first with a fixture repo that
has every one of the above. Measure and report resolution coverage: "% of import statements
resolved to a known module." Anything under ~90% and downstream retrieval is unreliable.

### 1.3 Store (`graph/store.py`) — Neo4j

Schema (see decisions.md D2 for the trade-off discussion):

- Nodes: `(:Symbol {repo_id, fqname, kind, path, start_line, end_line})`
  with a uniqueness constraint on `(repo_id, fqname)`.
  Modules are Symbols with `kind="module"` — one node label keeps traversal queries simple.
- Edges: `CONTAINS`, `IMPORTS`, `REFERENCES`, `CALLS`, `INHERITS`, `DECORATES`,
  each with `{line, type_only}` properties.
- Repo-scoped: `repo_id` on every node; index it. One database, many repos.

Snapshot policy: ingest at `pre_sha` only, and **re-ingest incrementally** after each batch
of edits (re-parse only changed files, replace their nodes). Don't version every commit —
you don't need history, you need the current state.

### 1.4 Queries (`graph/queries.py`)

- `dependents(ref, depth)` — variable-length incoming traversal:
  ```cypher
  MATCH (d:Symbol)-[:REFERENCES|CALLS|IMPORTS|INHERITS*1..$depth]->(s:Symbol
        {repo_id:$rid, fqname:$fq}) RETURN DISTINCT d
  ```
- `dependencies(ref, depth)` — the same, outgoing.
- `topo_modules(repo_id)` — condense SCCs (Python has circular imports; a cycle must migrate
  as one unit), then topologically sort the condensation. Tarjan in Python over the edges is
  fine and clearer than fighting Neo4j GDS; say that's a deliberate choice.
- `neighbourhood(ref, budget_tokens)` — ranked BFS: direct dependents first, then bases,
  then callers, then siblings in the same module; truncate to a token budget.
  **This is the function the retrieval ablation swaps.** Keep it behind the same signature
  so the embedding arm is a drop-in.

### 1.5 Relevance (`graph/relevance.py`) — the work list

Detect pydantic-touching symbols by signal:

| Signal | Detection |
|---|---|
| `BaseModel` subclass | `INHERITS` edge to a `pydantic.BaseModel` stub node (transitively!) |
| `BaseSettings` | same, plus flags the `pydantic-settings` package move |
| `@validator` / `@root_validator` | `DECORATES` edge from a pydantic decorator |
| `class Config` | nested class named `Config` inside a BaseModel subclass |
| `.dict()` / `.json()` / `.parse_obj()` / `.copy()` | attribute access on a value whose type traces to a model (best-effort; over-detect, it's cheap) |
| `Field(...)` kwargs | `regex=`, `allow_mutation=`, `const=`, `min_items=` |
| `__fields__`, `__config__`, `update_forward_refs` | name reference |
| custom `__get_validators__` | method name on any class |
| `constr/conint/condecimal` | call to a pydantic constructor |

Then group into `MigrationUnit`s per module, order by `topo_modules`, and emit batches.
Assign `est_difficulty` from the signal set — mechanical signals score 0–1, custom
validators and `__get_validators__` score 3. The agent uses this to route T1 vs T2.

## Acceptance criteria

- [ ] On a fixture repo with hand-labelled ground truth, `dependents`/`dependencies` achieve
      ≥95% precision and recall
- [ ] Import resolution coverage ≥90% on every corpus repo; per-repo number reported
- [ ] `topo_modules` handles circular imports (SCC condensation) — proven by a fixture
- [ ] `work_list()` on a corpus repo overlaps the human migration's changed files:
      **report recall — "the human touched N files; my work list contains M of them."**
      This number is the honest measure of whether Phase 1 works. Target ≥85%.
- [ ] Full ingest of the largest corpus repo completes in <60s

That fourth criterion is the phase's real test, and it's a great README chart.

## Pitfalls

- Don't build symbol-level nodes for *every* name — the graph explodes. Nodes are
  definitions; references are edges.
- Dynamic Python (getattr, factories, decorators that rewrite classes) is unresolvable.
  Accept it, measure it, mention it as a known limitation. That's a strength in interview.
- Don't let Neo4j block you. If ingest performance or driver friction eats more than two
  days, ship the networkx backend behind the same protocol and come back to it.
