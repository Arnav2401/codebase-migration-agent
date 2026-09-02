"""The migration loop as a LangGraph state machine (docs/phase-3-loop.md). API verified
interactively before wiring this: node functions return a PARTIAL dict of changed fields
(LangGraph merges it into the state), they do not mutate `AgentState` in place, and a plain
(non-frozen) dataclass works fine as the graph's state schema.

T1-only mode (no ModelClient at all) is a fully real, fully exercised path
(docs/phase-3-loop.md acceptance criteria: "T1-only is runnable as a config") and was
always the plan's first ablation arm (docs/decisions.md D4), not a fallback bolted on for
lack of an API key. T2 repair is also real now (docs/decisions.md D24/D25/D28) — a
single-shot repair attempt via `agent/repair.py`'s helpers, covering the target file plus
any local base classes it depends on, gated behind an injected `ModelClient`
(model_client.py). No `ANTHROPIC_API_KEY` exists in this environment; `GeminiModelClient`
verified the T2 path against Google's API instead.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from pmigrate.agent.budget import NoProgressDetector
from pmigrate.agent.diff import make_unified_diff
from pmigrate.agent.model_client import ModelClient
from pmigrate.agent.patch import apply_patch
from pmigrate.agent.repair import (
    build_repair_prompt,
    extract_rewritten_files,
    extract_target_file,
    find_related_files,
    repair_system_prompt,
)
from pmigrate.agent.state import AgentState, Edit
from pmigrate.codemod.engine import apply_rules
from pmigrate.codemod.rules import ALL_RULES
from pmigrate.graph.repo_files import read_py_files
from pmigrate.sandbox.protocol import Sandbox
from pmigrate.triage.classifier import RuleBasedClassifier
from pmigrate.triage.collect import collect_raw_failures
from pmigrate.triage.grouping import GroupedDiagnosis, group_raw_failures
from pmigrate.types import FailureClass, ImageRef, SandboxPolicy, TestOutcome

log = structlog.get_logger()

# docs/decisions.md D38: the order `repair()` picks among competing diagnoses when more
# than one class of failure is present in the same iteration. Cheap, mechanical,
# high-confidence fixes first (an import rename touches one line; a semantic validation
# difference needs the model to actually reason about behaviour) — fixing the mechanical
# ones first is also what tends to unblock the most other failures per repair attempt,
# since a single bad import can cascade into failures the model would otherwise have to
# wade through to see the real problem. PREEXISTING, THIRD_PARTY_PIN, and FLAKY are
# deliberately absent: I4 says PREEXISTING was never part of the scoring denominator,
# no source rewrite fixes a missing/pinned dependency (D26), and FLAKY-by-definition
# failures aren't a rewrite target — there is nothing here for the model to change.
_REPAIR_PRIORITY: tuple[FailureClass, ...] = (
    FailureClass.IMPORT_ERROR,
    FailureClass.CLASS_DEF_ERROR,
    FailureClass.REMOVED_API,
    FailureClass.VALIDATION_BEHAVIOUR,
    FailureClass.SERIALIZATION_DIFF,
    FailureClass.ERROR_MESSAGE_DIFF,
    FailureClass.UNKNOWN,
)


def _select_repair_target(candidates: list[GroupedDiagnosis]) -> GroupedDiagnosis | None:
    # first-occurrence-wins on a class collision (two groups of the same FailureClass,
    # split apart because they have different root frames) — deterministic given
    # `group_raw_failures`'s dict-iteration-order output, and a real tie-break policy
    # isn't worth building until evidence shows one repair attempt over the other
    # actually matters for fix rate.
    by_class: dict[FailureClass, GroupedDiagnosis] = {}
    for g in candidates:
        by_class.setdefault(g.diagnosis.cls, g)
    for cls in _REPAIR_PRIORITY:
        if cls in by_class:
            return by_class[cls]
    return None


def _failing_node_ids(outcomes: tuple[TestOutcome, ...]) -> list[str]:
    return [o.node_id for o in outcomes if o.status in ("failed", "error")]


def _module_name_from_path(path: str) -> str:
    # Display-only label for Edit records (grouping in demo/trace output) — NOT the
    # resolver's fqname (graph/resolver.py's _path_to_fqname, which handles src/ layout
    # detection and is private to that module). Good enough for a report label; nothing
    # downstream parses this value structurally.
    without_ext = path[: -len(".py")] if path.endswith(".py") else path
    parts = without_ext.split("/")
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_migration_graph(
    *,
    sandbox: Sandbox,
    image: ImageRef,
    source_root: Path,
    overlay_root: Path,
    policy: SandboxPolicy,
    model_client: ModelClient | None = None,
    no_progress_threshold: int = 2,
    use_triage: bool = True,
) -> Any:
    # Any: langgraph's CompiledStateGraph is generic over 4 type params callers never
    # interact with beyond .invoke() — parametrizing it precisely here would add real
    # complexity for no downstream benefit.
    #
    # use_triage (docs/decisions.md D40): the ONE ablation axis eval/harness.py needs to
    # produce phase-4-triage.md's "measured pass-rate lift vs. Phase 3" number. `classify`
    # still runs unconditionally either way — it's cheap, deterministic, and its output
    # (real diagnosed failures) is exactly the raw material the harness dumps for hand-
    # labelling regardless of which arm produced it. Only whether that output gets ACTED
    # on toggles: `route()` skips the all-PREEXISTING check (D37) and `repair()` skips
    # diagnosis-routed target selection (D38), falling back to the pre-D37/D38 shape —
    # `collect_failure_texts` dumping every raw failure into one prompt, repair attempted
    # on any failure regardless of whether it's already known-broken at baseline. That
    # pre-existing fallback path is exactly why `collect_failure_texts` was kept in
    # `agent/repair.py` rather than deleted once D38 stopped calling it directly.
    no_progress = NoProgressDetector(repeat_threshold=no_progress_threshold)
    classifier = RuleBasedClassifier()

    def edit_t1(state: AgentState) -> dict[str, Any]:
        """Processes the ENTIRE remaining work list in one call, not just
        `state.current_batch` — a real design fix, not the original plan. The first real
        end-to-end run (docs/decisions.md D17) showed why: with one-unit-at-a-time
        processing gated on `route()` only advancing after a fully green test run, a
        SINGLE early failure (in unit 1 of 9) meant units 2-9 never got their (needed,
        independent, purely mechanical) codemod fixes applied at all — `control.py`'s own
        `pydantic.BaseSettings` usage sat untouched while the loop gave up after `plugin.py`
        alone. That per-unit gating makes sense for T2/repair, where you want tight
        feedback per LLM call — it actively works against T1, which is cheap, deterministic,
        and doesn't need test feedback to decide whether to apply a rename. Matches
        docs/phase-3-loop.md's own framing: "T1 codemods run first, unconditionally, before
        any LLM involvement" — unconditionally, for the WHOLE repo, not unit-by-unit.

        Also runs T1 over every first-party .py file in the repo, not only the files
        `state.work_list` names — a second real gap (docs/decisions.md D19). `work_list`
        comes from `relevance.py`'s signal detection, which is built for symbol-level T2
        targeting (class inherits BaseModel/BaseSettings, `.dict()`-shaped calls, nested
        Config) — it has no detector for "this file merely references
        `pydantic.BaseSettings` in a type annotation", so a file like that never enters
        work_list at all and sat untouched even after the D18 fix above (D18 only reaches
        files already IN the list, eagerly instead of one-at-a-time). T1 rules are cheap,
        deterministic, and test-gated — there's no reason to scope them to relevance.py's
        narrower planning set. work_list still drives ordering/module naming for edit
        provenance; it no longer gates which files T1 is allowed to touch.
        """
        remaining_batches = state.work_list[state.cursor :]
        # `state.cursor > 0` distinguishes "already processed, nothing left" (a later
        # call, once this node has run before) from "zero MigrationUnits to begin with"
        # (the very first call, work_list==[] because relevance.py found no T1-flagged
        # signal anywhere in the repo) — docs/decisions.md D41. Only the former should
        # skip the loop below: the full-repo file-copy is NOT gated on work_list content
        # (see this function's own docstring), so a signal-less repo still needs its
        # files copied into overlay_root before repair() can read any of them. Found
        # live: eval/harness.py's first real run against a minimal fixture with zero T1
        # signals crashed repair() with FileNotFoundError, since overlay_root was never
        # populated at all.
        if not remaining_batches and state.cursor > 0:
            return {}

        module_by_path: dict[str, str] = {}
        for batch in remaining_batches:
            for unit in batch:
                module_by_path[unit.path] = unit.module

        all_paths = sorted(read_py_files(source_root).keys())
        for path in all_paths:
            module_by_path.setdefault(path, _module_name_from_path(path))

        new_edits = list(state.edits)
        for path in all_paths:
            src_file = source_root / path
            dst_file = overlay_root / path
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            if not dst_file.exists():
                dst_file.write_text(src_file.read_text())

            before = dst_file.read_text()
            after, rule_edits = apply_rules(before, path, ALL_RULES)
            if after == before:
                continue

            diff_text = make_unified_diff(path, before, after)
            result = apply_patch(overlay_root, diff_text)
            if result.applied:
                new_edits.append(
                    Edit(
                        source="T1",
                        unit_module=module_by_path[path],
                        files_changed=result.files_changed,
                        diff=diff_text,
                        rule_edits=tuple(rule_edits),
                    )
                )
            # a rejected patch (invariant violation, or a syntax break git apply itself
            # caught) is silently skipped here rather than aborting the whole run — T1
            # rules are heuristic (protocol.py's module docstring) and the next
            # run_tests call is what actually judges whether skipping was fine.

        log.info(
            "agent.edit_t1",
            trace_id=state.trace_id,
            repo_id=state.repo.repo_id,
            files_scanned=len(all_paths),
            edits_applied=len(new_edits) - len(state.edits),
        )
        return {"edits": new_edits, "cursor": len(state.work_list)}

    def repair(state: AgentState) -> dict[str, Any]:
        """T2: a targeted repair attempt against the current failure(s), covering the
        target file PLUS any local base classes it depends on (docs/decisions.md D28) —
        not single-file only, as originally cut (D25). docs/decisions.md D38: now routes
        target selection through `state.diagnoses` (Phase 4 triage) rather than the flat
        "group failures naively and hand the model the trimmed log" approach
        docs/phase-3-loop.md originally described — `route()` already guarantees at
        least one non-PREEXISTING diagnosis exists by the time this node runs, so this
        picks ONE concrete failure class to fix per attempt (`_select_repair_target`)
        instead of dumping every failure text into one prompt regardless of cause.

        Re-derives `state.diagnoses` down to `GroupedDiagnosis` (full `RawFailure` text,
        not just `Diagnosis.evidence`'s ~200-char snippet) via `group_raw_failures`
        rather than threading a second state field through `classify_node` — cheap to
        recompute (pure function of `state.last_run`/`state.repo.baseline`, both already
        in state) and keeps `AgentState.diagnoses` exactly the `list[Diagnosis]` shape
        `Classifier.classify()` documents.

        Considers `collection_errors` as well as failing `outcomes` (via
        `triage.collect.collect_raw_failures`) — a collection error blocks an entire test
        file and is NOT a `TestOutcome` at all (results.py keeps the two separate), so
        outcome-only scanning would silently never attempt a repair when collection
        errors are the only failure signal at all (exactly the "0 passed / 0 total, all
        collection errors" state a fresh migration starts in).
        """
        if model_client is None or state.last_run is None:
            return {}
        raw_failures = collect_raw_failures(state.last_run)
        if not raw_failures:
            return {}

        chosen: GroupedDiagnosis | None = None
        if use_triage:
            grouped = group_raw_failures(raw_failures, state.repo.baseline)
            repairable = [
                g
                for g in grouped
                if g.diagnosis.cls
                not in (FailureClass.PREEXISTING, FailureClass.THIRD_PARTY_PIN, FailureClass.FLAKY)
            ]
            chosen = _select_repair_target(repairable)
            if chosen is None:
                log.warning(
                    "agent.repair_no_target", trace_id=state.trace_id, repo_id=state.repo.repo_id
                )
                return {}  # no state change; no_progress eventually catches a real stall
            failure_texts = tuple(f.text for f in chosen.raw_failures)
        else:
            # docs/decisions.md D40: the pre-D38 "Phase 3" shape — every raw failure
            # dumped into one prompt, no per-class targeting at all.
            failure_texts = tuple(f.text for f in raw_failures)

        target_path = extract_target_file(failure_texts, overlay_root)
        if target_path is None:
            log.warning(
                "agent.repair_no_target",
                trace_id=state.trace_id,
                repo_id=state.repo.repo_id,
                cls=chosen.diagnosis.cls.value if chosen else None,
            )
            return {}  # no state change; no_progress eventually catches a real stall

        target_before = (overlay_root / target_path).read_text()
        related_paths = find_related_files(target_path, target_before, overlay_root)
        paths = (target_path, *related_paths)
        before_by_path = {p: (overlay_root / p).read_text() for p in paths}
        prompt = build_repair_prompt(before_by_path, failure_texts)

        try:
            response = model_client.complete(system=repair_system_prompt(), prompt=prompt)
        except Exception as exc:
            # A real ModelClient (unlike FakeModelClient, which by construction never
            # raises) can fail for reasons entirely outside this loop's control — a
            # network error, a quota/billing rejection, a malformed response.
            # docs/decisions.md D24: found live wiring in the first real client
            # (GeminiModelClient) that this call had zero exception handling and the
            # outgoing `repair` -> `run_tests` edge was unconditional, so a failure here
            # would have crashed `.invoke()` — the same gap D22 already found and fixed
            # one layer down, in codemod rules. `Status` already has "failed" for exactly
            # this outcome; route() below now actually reaches it instead of crashing.
            log.warning(
                "agent.repair_failed",
                trace_id=state.trace_id,
                repo_id=state.repo.repo_id,
                error=str(exc),
            )
            return {"status": "failed"}

        spend = state.budget.spend(response.usd_cost, response.tokens_in, response.tokens_out)
        rewritten = extract_rewritten_files(response.text)
        if not rewritten:
            log.warning(
                "agent.repair_no_edit",
                trace_id=state.trace_id,
                repo_id=state.repo.repo_id,
                target_path=target_path,
                related_paths=list(related_paths),
                cls=chosen.diagnosis.cls.value if chosen else None,
                strategy=chosen.diagnosis.strategy if chosen else None,
            )
            return {"budget": spend}  # spent money on the attempt even if it produced nothing

        new_edits = list(state.edits)
        for path, after in rewritten.items():
            before = before_by_path.get(path)
            if before is None:
                # the model named a file it was never shown — never trust an unshown
                # path enough to write to it; only apply edits to files this call
                # actually sent as context.
                log.warning(
                    "agent.repair_unknown_path",
                    trace_id=state.trace_id,
                    repo_id=state.repo.repo_id,
                    path=path,
                )
                continue
            if after == before:
                continue

            diff_text = make_unified_diff(path, before, after)
            result = apply_patch(overlay_root, diff_text)  # same I1-I3 chokepoint T1 uses
            if result.applied:
                new_edits.append(
                    Edit(
                        source="T2",
                        unit_module=_module_name_from_path(path),
                        files_changed=result.files_changed,
                        diff=diff_text,
                    )
                )
            log.info(
                "agent.repair_applied" if result.applied else "agent.repair_rejected",
                trace_id=state.trace_id,
                repo_id=state.repo.repo_id,
                path=path,
                usd_cost=response.usd_cost,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                cls=chosen.diagnosis.cls.value if chosen else None,
                strategy=chosen.diagnosis.strategy if chosen else None,
                violations=[v.message for v in result.violations] if not result.applied else [],
                # violations=[] with applied=False means the rejection wasn't an I1-I3
                # invariant at all — it was a git-apply or post-apply syntax failure,
                # whose detail only lives in `stderr` (agent/patch.py). Found live
                # (D26): the first `agent.repair_rejected` this project ever logged
                # carried empty violations and no stderr, which made the rejection
                # reason genuinely undiagnosable after the fact — exactly the kind of
                # silent-failure-path gap CLAUDE.md's review checklist calls out.
                stderr=result.stderr if not result.applied else None,
            )
        return {"edits": new_edits, "budget": spend}

    def run_tests_node(state: AgentState) -> dict[str, Any]:
        """docs/decisions.md D46: also updates `cumulative_outcomes` — the new run's
        outcomes overwrite prior entries for the same `node_id`, everything else carries
        forward. `selection`-narrowed runs (every call after the first) only re-test
        previously-failing node_ids, so without this, `state.last_run` alone loses track
        of every test that was already confirmed passing and never touched again —
        exactly the gap that made a real corpus run's scoring undercount pass_rate."""
        selection = _failing_node_ids(state.last_run.outcomes) if state.last_run else None
        start = time.time()
        run = sandbox.run_tests(image, overlay_root, policy, selection=selection)
        cumulative_outcomes = {**state.cumulative_outcomes, **{o.node_id: o for o in run.outcomes}}
        # PLAN.md §7 op metrics (10: iterations-to-green, 8: p95 wall-clock) — logged from
        # Phase 3 as the plan requires ("log from Phase 3, never retroactively"), via plain
        # structlog events rather than a `trace/` module: `trace/` is PLAN.md's Phase 6
        # deliverable (JSONL+SQLite, replayable), and Phase 6 is explicitly locked until
        # docs/results/main.md has real measured numbers (CLAUDE.md's build-order rule).
        # These events ARE the raw material Phase 5/6 tooling will later aggregate — the
        # goal here is "don't lose the data", not "build the replay system early".
        passed = sum(1 for o in run.outcomes if o.status == "passed")
        log.info(
            "agent.run_tests",
            trace_id=state.trace_id,
            repo_id=state.repo.repo_id,
            iteration=state.budget.iterations + 1,
            passed=passed,
            total=len(run.outcomes),
            collection_errors=len(run.collection_errors),
            duration_s=time.time() - start,
        )
        return {
            "last_run": run,
            "cumulative_outcomes": cumulative_outcomes,
            "budget": state.budget.next_iteration(),
        }

    def classify_node(state: AgentState) -> dict[str, Any]:
        """Phase 4 (docs/decisions.md D36): classifies `state.last_run`'s failures against
        `state.repo.baseline`, populating the `diagnoses` field that's existed on
        `AgentState` since it was first scaffolded but never had anything to fill it.
        `route()` below uses this for one concrete, valuable thing `state.last_run` alone
        couldn't tell it: whether every remaining failure is `PREEXISTING` (failed at the
        v1 baseline too, per I4) — a real distinction `_failing_node_ids`-based routing
        was blind to before this, which meant a run with `model_client` set would
        genuinely attempt (and spend real money on) T2 repair against a test that was
        broken before the migration ever started, something the agent was never going to
        be able to (or supposed to) fix.
        """
        if state.last_run is None:
            return {"diagnoses": []}
        diagnoses = classifier.classify(state.last_run, state.repo.baseline)
        if diagnoses:
            log.info(
                "agent.classify",
                trace_id=state.trace_id,
                repo_id=state.repo.repo_id,
                classes=[d.cls.value for d in diagnoses],
                preexisting=sum(1 for d in diagnoses if d.cls == FailureClass.PREEXISTING),
            )
        return {"diagnoses": diagnoses}

    def finalize(state: AgentState) -> dict[str, Any]:
        result = {} if state.status != "running" else {"status": "done"}
        log.info(
            "agent.finalize",
            trace_id=state.trace_id,
            repo_id=state.repo.repo_id,
            status=result.get("status", state.status),
            total_edits=len(state.edits),
            iterations=state.budget.iterations,
            usd_spent=state.budget.usd_spent,
            wallclock_s=time.time() - state.budget.started_at,
        )
        return result

    def route(state: AgentState) -> str:
        breach = state.budget.exceeded()
        if breach is not None:
            return "budget_exceeded"

        run = state.last_run
        if run is None:
            return "finalize"  # shouldn't happen — run_tests always precedes route

        failing = _failing_node_ids(run.outcomes)
        if not failing and not run.collection_errors:
            if state.current_batch is None:
                return "finalize"
            return "next_unit"

        # docs/decisions.md D36: raw failures/collection_errors being non-empty doesn't
        # mean there's real work left — if EVERY classified diagnosis is PREEXISTING
        # (failed at the v1 baseline too), I4 says none of it counts, and there's
        # nothing left the agent should be trying to fix. Without this, a run with
        # `model_client` set would genuinely spend real money on T2 repair against a
        # test that was already broken before the migration ever started.
        # use_triage gate (D40): this is Phase 4's own behavior, not Phase 3's — the
        # "Phase 3 arm" of the eval harness's ablation must NOT get this skip, or the
        # comparison would be measuring something other than what D36/D37 actually added.
        if (
            use_triage
            and state.diagnoses
            and all(d.cls == FailureClass.PREEXISTING for d in state.diagnoses)
        ):
            if state.current_batch is None:
                return "finalize"
            return "next_unit"

        # docs/decisions.md D25: collection errors are folded into the no-progress
        # signature too, not just outcome node_ids — a fresh migration commonly starts
        # with 0 outcomes recorded at all (everything blocked at collection), which
        # would otherwise make `failing` permanently empty and falsely declare "no
        # progress" on the very first repair attempt regardless of whether repair is
        # actually reducing the number of collection errors.
        if no_progress.observe([*failing, *run.collection_errors]):
            return "no_progress"

        return "repair" if model_client is not None else "finalize"

    def mark_status(target: str) -> Any:
        def _node(state: AgentState) -> dict[str, Any]:
            return {"status": target}

        return _node

    def route_after_repair(state: AgentState) -> str:
        # `repair()` sets status="failed" itself on a caught model-client exception
        # (docs/decisions.md D24) — this is the conditional edge that actually acts on
        # it, rather than the old unconditional `repair -> run_tests` edge that would
        # have run another test cycle on a state repair() never actually touched.
        return "failed" if state.status == "failed" else "continue"

    graph = StateGraph(AgentState)
    graph.add_node("edit_t1", edit_t1)
    graph.add_node("run_tests", run_tests_node)
    graph.add_node("classify", classify_node)
    graph.add_node("repair", repair)
    graph.add_node("finalize", finalize)
    graph.add_node("mark_budget_exceeded", mark_status("budget_exceeded"))
    graph.add_node("mark_no_progress", mark_status("no_progress"))

    graph.set_entry_point("edit_t1")
    graph.add_edge("edit_t1", "run_tests")
    graph.add_edge("run_tests", "classify")
    graph.add_conditional_edges(
        "classify",
        route,
        {
            "next_unit": "edit_t1",
            "repair": "repair",
            "finalize": "finalize",
            "budget_exceeded": "mark_budget_exceeded",
            "no_progress": "mark_no_progress",
        },
    )
    graph.add_conditional_edges(
        "repair",
        route_after_repair,
        {"continue": "run_tests", "failed": END},
    )
    graph.add_edge("mark_budget_exceeded", END)
    graph.add_edge("mark_no_progress", END)
    graph.add_edge("finalize", END)

    return graph.compile()
