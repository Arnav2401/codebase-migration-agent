from dataclasses import dataclass, field
from pathlib import Path

from pmigrate.agent.budget import BudgetState
from pmigrate.agent.graph import (
    _repair_candidates_in_priority_order,
    _select_repair_target,
    build_migration_graph,
)
from pmigrate.agent.model_client import FakeModelClient, ModelResponse
from pmigrate.agent.state import AgentState
from pmigrate.triage.collect import RawFailure
from pmigrate.triage.grouping import GroupedDiagnosis
from pmigrate.types import (
    BaselineResult,
    Diagnosis,
    FailureClass,
    ImageRef,
    MigrationUnit,
    RepoSpec,
    SandboxPolicy,
    TestOutcome,
    TestRun,
)


@dataclass
class FakeSandbox:
    """Test double for the Sandbox protocol (sandbox/protocol.py) — scripted TestRun
    results consumed in order, so the graph's control flow (routing, looping, budget
    checks) can be exercised without Docker."""

    responses: list[TestRun]
    run_calls: list = field(default_factory=list)
    _index: int = 0

    def build(self, repo, pydantic):  # type: ignore[no-untyped-def]
        raise NotImplementedError("not exercised by these tests")

    def run_tests(self, image, workdir_overlay, policy, selection=None):  # type: ignore[no-untyped-def]
        self.run_calls.append(selection)
        response = self.responses[min(self._index, len(self.responses) - 1)]
        self._index += 1
        return response


@dataclass
class FakeRetrieval:
    """Test double for the Retrieval protocol (agent/retrieval.py) — a scripted answer,
    recording every call, so a test can prove repair() actually calls the INJECTED
    strategy (and uses its answer) rather than silently falling back to
    find_related_files."""

    response: tuple[str, ...]
    calls: list = field(default_factory=list)

    def related_files(self, target_path, target_before, repo_root):  # type: ignore[no-untyped-def]
        self.calls.append((target_path, target_before, repo_root))
        return self.response


def _repo(baseline: BaselineResult | None = None) -> RepoSpec:
    return RepoSpec(
        repo_id="acme__widgets",
        url="https://example.invalid/acme/widgets",
        pre_sha="a" * 40,
        post_sha="b" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest", "-q"),
        baseline=baseline,
    )


def _image() -> ImageRef:
    return ImageRef(
        tag="img",
        repo_id="acme__widgets",
        sha="a" * 40,
        pydantic="v2",
        deps_hash="x",
        test_cmd=("pytest",),
    )


def _passed_run() -> TestRun:
    return TestRun(
        outcomes=(TestOutcome("t.py::test_a", "passed", 0.1, None, None, None),),
        collection_errors=(),
        exit_code=0,
        duration_s=0.1,
        truncated=False,
    )


def _failed_run(
    node_id: str = "t.py::test_a",
    traceback: str = "app/models.py:1: in <module>\n    x = 1\nE   AssertionError: boom",
) -> TestRun:
    # traceback defaults to a realistic shape (a first-party path repair.extract_target_file
    # can actually find) rather than the literal string "traceback" — repair() now declines
    # to call the model at all when it can't identify a target file to apply a fix to, so a
    # placeholder traceback would silently make every repair-path test stop exercising
    # repair() without any assertion failing to say so.
    return TestRun(
        outcomes=(TestOutcome(node_id, "failed", 0.1, "boom", traceback, None),),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )


def _setup_source(tmp_path: Path, content: str = "x = m.dict()\n") -> tuple[Path, Path]:
    source_root = tmp_path / "source"
    overlay_root = tmp_path / "overlay"
    source_root.mkdir()
    overlay_root.mkdir()
    (source_root / "app").mkdir()
    (source_root / "app" / "models.py").write_text(content)
    return source_root, overlay_root


def _unit(path: str = "app/models.py", module: str = "app.models") -> MigrationUnit:
    return MigrationUnit(
        module=module,
        path=path,
        symbols=(),
        signals=frozenset({"mechanical_call"}),
        est_difficulty=1,
    )


def test_t1_only_single_unit_passes_and_finalizes(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    sandbox = FakeSandbox(responses=[_passed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])
    result = graph.invoke(state)

    assert result["status"] == "done"
    assert len(result["edits"]) == 1
    assert result["edits"][0].source == "T1"
    assert (overlay_root / "app" / "models.py").read_text() == "x = m.model_dump()\n"


def test_t1_only_processes_whole_work_list_before_first_test_run(tmp_path: Path) -> None:
    # T1 is applied EAGERLY across the entire work list in one edit_t1 call, then tested
    # once — not one-unit-at-a-time gated on a green run. docs/decisions.md D17: the first
    # real end-to-end run showed that per-unit gating left later units' (independent,
    # purely mechanical) fixes never applied at all once an earlier unit's test failed.
    source_root, overlay_root = _setup_source(tmp_path)
    (source_root / "app" / "settings.py").write_text("y = m.json()\n")
    sandbox = FakeSandbox(responses=[_passed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    state = AgentState(
        repo=_repo(),
        work_list=[[_unit()], [_unit(path="app/settings.py", module="app.settings")]],
    )
    result = graph.invoke(state)

    assert result["status"] == "done"
    assert result["cursor"] == 2
    assert len(sandbox.run_calls) == 1  # a single test run, after BOTH units were fixed
    assert len(result["edits"]) == 2
    assert (overlay_root / "app" / "settings.py").read_text() == "y = m.model_dump_json()\n"


def test_no_model_client_finalizes_immediately_on_persistent_failure(tmp_path: Path) -> None:
    # T1-only mode has no repair capability — a failure it can't fix should finalize
    # (not loop forever), matching graph.py's documented "repair only if model_client".
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # nothing for T1 to fix
    sandbox = FakeSandbox(responses=[_failed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])
    result = graph.invoke(state)

    assert result["status"] == "done"
    assert len(sandbox.run_calls) == 1  # never looped into repair


def test_budget_exceeded_stops_the_loop(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path)
    sandbox = FakeSandbox(responses=[_passed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    # max_iterations=0: the first run_tests call's next_iteration() immediately breaches
    state = AgentState(repo=_repo(), work_list=[[_unit()]], budget=BudgetState(max_iterations=0))
    result = graph.invoke(state)

    assert result["status"] == "budget_exceeded"


def test_no_progress_detected_when_repair_does_not_help(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    # same failing test twice in a row, even with a model_client attempting repair
    sandbox = FakeSandbox(responses=[_failed_run(), _failed_run()])
    fake_model = FakeModelClient(
        responses=[],
        default_response=ModelResponse(text="attempt", usd_cost=0.01, tokens_in=5, tokens_out=5),
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])
    result = graph.invoke(state)

    assert result["status"] == "no_progress"
    assert len(sandbox.run_calls) == 2
    assert len(fake_model.calls) >= 1  # repair genuinely attempted before giving up


def test_progress_between_repairs_does_not_trigger_no_progress(tmp_path: Path) -> None:
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    # first failure on test_a, second run a DIFFERENT failure on test_b — real progress,
    # should keep going rather than falsely declaring no-progress
    sandbox = FakeSandbox(
        responses=[_failed_run("t.py::test_a"), _failed_run("t.py::test_b"), _passed_run()]
    )
    fake_model = FakeModelClient(
        responses=[],
        default_response=ModelResponse(text="attempt", usd_cost=0.01, tokens_in=5, tokens_out=5),
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])
    result = graph.invoke(state)

    assert result["status"] == "done"
    assert len(sandbox.run_calls) == 3
    # doubles as the accumulation check: two real repair() calls (one per failed run),
    # both landing on "no_edit" since "attempt" has no "File:" marker to rewrite -- a
    # node returning {"repair_attempts": [...]} must build the FULL new list itself
    # (LangGraph replaces the key wholesale), the same pattern cumulative_outcomes uses.
    assert [a.outcome for a in result["repair_attempts"]] == ["no_edit", "no_edit"]


def test_early_unit_failure_does_not_block_later_units_t1_fixes(tmp_path: Path) -> None:
    # the exact D17 regression: unit 1 (app/models.py) has a bug T1 can't fix (content is
    # untouched, so the test stays red); unit 2 (app/settings.py) has an INDEPENDENT
    # mechanical .json() call that T1 CAN fix. Both units' codemods must run regardless of
    # whether unit 1's test ever passes.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # nothing for T1 to fix
    (source_root / "app" / "settings.py").write_text("y = m.json()\n")
    sandbox = FakeSandbox(responses=[_failed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    state = AgentState(
        repo=_repo(),
        work_list=[[_unit()], [_unit(path="app/settings.py", module="app.settings")]],
    )
    result = graph.invoke(state)

    # settings.py got its fix applied even though models.py's test never passed
    assert (overlay_root / "app" / "settings.py").read_text() == "y = m.model_dump_json()\n"
    assert any(e.unit_module == "app.settings" for e in result["edits"])


@dataclass
class _RaisingModelClient:
    """Test double for a model client that fails the way a real one can — a network
    error, a quota rejection — unlike FakeModelClient, which by construction never
    raises. Used to verify the D24 fix: repair() must catch this and route to
    status="failed" instead of crashing graph.invoke()."""

    calls: list = field(default_factory=list)

    def complete(self, system: str, prompt: str) -> ModelResponse:
        self.calls.append((system, prompt))
        raise RuntimeError("simulated: network error calling the model")


def test_model_client_failure_in_repair_ends_the_run_as_failed_not_a_crash(
    tmp_path: Path,
) -> None:
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    sandbox = FakeSandbox(responses=[_failed_run()])
    raising_client = _RaisingModelClient()
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=raising_client,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)  # must not raise

    assert result["status"] == "failed"
    assert len(raising_client.calls) == 1
    assert len(sandbox.run_calls) == 1  # never looped back into a second test run
    assert [a.outcome for a in result["repair_attempts"]] == ["model_error"]
    assert result["repair_attempts"][0].usd_cost == 0.0  # complete() raised before returning a cost


def test_t1_fixes_files_outside_the_work_list(tmp_path: Path) -> None:
    # the exact D19 regression: fastapi_plugins/settings.py used `pydantic.BaseSettings`
    # only as a bare parameter type annotation — a shape relevance.py's signal detection
    # never flags, so the file was never in work_list at all. T1 must still reach it,
    # since its codemods are cheap/deterministic and shouldn't be scoped to relevance.py's
    # narrower symbol-targeting set.
    source_root, overlay_root = _setup_source(tmp_path)
    (source_root / "app" / "extra.py").write_text("z = m.json()\n")  # NOT in work_list
    sandbox = FakeSandbox(responses=[_passed_run()])
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])  # only app/models.py listed
    result = graph.invoke(state)

    assert (overlay_root / "app" / "extra.py").read_text() == "z = m.model_dump_json()\n"
    assert any(e.unit_module == "app.extra" for e in result["edits"])


def test_repair_applies_a_multi_file_response_end_to_end(tmp_path: Path) -> None:
    # the exact real shape found live (docs/decisions.md D26/D28): the failing test
    # names a class (AppSettings) that only inherits its broken field from a DIFFERENT
    # file (base.py's BrokenBase) — repair must find, send, and apply changes to BOTH.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    (source_root / "app" / "base.py").write_text("class BrokenBase:\n    val: str = None\n")
    (source_root / "app" / "app_settings.py").write_text(
        "from app.base import BrokenBase\n\n\nclass AppSettings(BrokenBase):\n    pass\n"
    )
    traceback = (
        "tests/test_app.py:5: in <module>\n"
        "    AppSettings()\n"
        "E   pydantic_core._pydantic_core.ValidationError: 1 validation error for AppSettings"
    )
    sandbox = FakeSandbox(responses=[_failed_run(traceback=traceback), _passed_run()])
    multi_file_response = (
        "File: app/base.py\n```python\nclass BrokenBase:\n    val: str | None = None\n```\n\n"
        "File: app/app_settings.py\n```python\n"
        "from app.base import BrokenBase\n\n\nclass AppSettings(BrokenBase):\n    pass\n"
        "```\n"  # identical to before — must NOT produce a spurious edit
    )
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(text=multi_file_response, usd_cost=0.01, tokens_in=10, tokens_out=10)
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)

    assert result["status"] == "done"
    assert (overlay_root / "app" / "base.py").read_text() == (
        "class BrokenBase:\n    val: str | None = None\n"
    )
    # the unchanged file must NOT show up as a spurious edit
    assert not any(e.unit_module == "app.app_settings" for e in result["edits"])
    assert any(e.unit_module == "app.base" and e.source == "T2" for e in result["edits"])
    assert [a.outcome for a in result["repair_attempts"]] == ["applied"]
    assert result["repair_attempts"][0].usd_cost == 0.01


def test_repair_uses_the_injected_retrieval_strategy_instead_of_find_related_files(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D60: an injected Retrieval must actually drive what context
    # repair() sends -- not just get called and then be ignored in favor of the old
    # find_related_files heuristic.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    (source_root / "app" / "extra_context.py").write_text("EXTRA_MARKER = 1\n")
    traceback = "app/models.py:1: in <module>\nE   AssertionError: boom"
    sandbox = FakeSandbox(responses=[_failed_run(traceback=traceback), _passed_run()])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/models.py\n```python\nx = 2\n```\n",
                usd_cost=0.01,
                tokens_in=5,
                tokens_out=5,
            )
        ]
    )
    fake_retrieval = FakeRetrieval(response=("app/extra_context.py",))

    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
        retrieval=fake_retrieval,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    graph.invoke(state)

    assert len(fake_retrieval.calls) == 1
    assert fake_retrieval.calls[0][0] == "app/models.py"
    _system, prompt = fake_model.calls[0]
    assert "EXTRA_MARKER" in prompt  # the injected strategy's answer reached the prompt


def test_repair_records_a_rejected_attempt_when_nothing_the_model_proposes_lands(
    tmp_path: Path,
) -> None:
    # the model responds, but every proposed file either names a path never shown to it
    # (agent.repair_unknown_path -- the same I1-I3 guard that discarded a hallucinated
    # path live on cmudig__draco2, docs/results/triage.md) or is a no-op -- distinct from
    # "no_edit" above, where the model returns nothing to rewrite at all.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    sandbox = FakeSandbox(responses=[_failed_run(), _failed_run()])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/never_shown.py\n```python\nx = 2\n```\n",
                usd_cost=0.01,
                tokens_in=10,
                tokens_out=10,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)

    assert [a.outcome for a in result["repair_attempts"]] == ["rejected"]
    assert result["repair_attempts"][0].usd_cost == 0.01


def test_repair_records_a_no_target_attempt_when_no_candidate_has_a_findable_target(
    tmp_path: Path,
) -> None:
    # the ONLY failure's ONLY first-party-ish frame is a test file itself --
    # extract_target_file correctly refuses to point at it (I1), and with no other
    # candidate to fall through to (docs/decisions.md D50), chosen stays None entirely.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    traceback = (
        "tests/test_control.py:25: in <module>\n"
        "    class Dummy(config: pydantic.BaseSettings=None):\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    sandbox = FakeSandbox(responses=[_failed_run(traceback=traceback)])
    fake_model = FakeModelClient(responses=[])  # never called -- no target, no model call
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)

    assert fake_model.calls == []
    assert [a.outcome for a in result["repair_attempts"]] == ["no_target"]
    assert result["repair_attempts"][0].cls is None
    # no diagnosis was ever chosen, but the raw failures it couldn't find a target for
    # are still attributed to the attempt -- honest about what was tried and missed.
    assert result["repair_attempts"][0].node_ids == ("t.py::test_a",)


def _grouped(cls: FailureClass, node_id: str = "t.py::test_a") -> GroupedDiagnosis:
    raw = RawFailure(node_id=node_id, text=f"failure for {cls.value}")
    diagnosis = Diagnosis(
        node_ids=(node_id,),
        cls=cls,
        confidence=0.9,
        evidence="evidence",
        suspect_symbols=(),
        strategy="some_strategy",
    )
    return GroupedDiagnosis(diagnosis=diagnosis, raw_failures=(raw,))


def test_select_repair_target_prefers_import_error_over_validation_behaviour() -> None:
    # docs/decisions.md D38's priority order: mechanical/high-confidence fixes (a bad
    # import) get picked over a class that needs the model to reason about behaviour,
    # even when the validation failure is listed first.
    candidates = [_grouped(FailureClass.VALIDATION_BEHAVIOUR), _grouped(FailureClass.IMPORT_ERROR)]
    chosen = _select_repair_target(candidates)
    assert chosen is not None
    assert chosen.diagnosis.cls == FailureClass.IMPORT_ERROR


def test_select_repair_target_returns_none_when_nothing_is_repairable() -> None:
    # PREEXISTING/THIRD_PARTY_PIN/FLAKY are excluded from _REPAIR_PRIORITY entirely —
    # repair() itself is responsible for filtering these out before calling this, but the
    # selector should also refuse to pick one if it's ever handed one by mistake.
    candidates = [_grouped(FailureClass.PREEXISTING), _grouped(FailureClass.THIRD_PARTY_PIN)]
    assert _select_repair_target(candidates) is None


def test_select_repair_target_returns_none_for_empty_candidates() -> None:
    assert _select_repair_target([]) is None


def test_repair_candidates_in_priority_order_returns_all_repairable_candidates_in_order() -> None:
    # docs/decisions.md D50: repair() needs the FULL ordered list, not just the winner,
    # so it can fall through past a target-less top candidate.
    candidates = [
        _grouped(FailureClass.UNKNOWN),
        _grouped(FailureClass.VALIDATION_BEHAVIOUR),
        _grouped(FailureClass.IMPORT_ERROR),
    ]
    ordered = _repair_candidates_in_priority_order(candidates)
    assert [g.diagnosis.cls for g in ordered] == [
        FailureClass.IMPORT_ERROR,
        FailureClass.VALIDATION_BEHAVIOUR,
        FailureClass.UNKNOWN,
    ]


def test_repair_candidates_in_priority_order_excludes_nothing_extra() -> None:
    candidates = [_grouped(FailureClass.PREEXISTING), _grouped(FailureClass.THIRD_PARTY_PIN)]
    # PREEXISTING/THIRD_PARTY_PIN aren't in _REPAIR_PRIORITY at all -- repair() filters
    # these out before calling this, but the ordering function itself should just as
    # correctly produce an empty list if it's ever handed them anyway.
    assert _repair_candidates_in_priority_order(candidates) == []


def test_repair_only_sends_the_model_the_chosen_diagnosis_failure_text(tmp_path: Path) -> None:
    # docs/decisions.md D38: when two DIFFERENT failure classes are present in the same
    # iteration, repair() must route on the higher-priority one (IMPORT_ERROR here) and
    # must NOT dump the validation failure's text into the same prompt — the model should
    # only see evidence for the failure it was actually asked to fix.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # T1 can't fix this
    import_traceback = (
        "app/models.py:1: in <module>\n"
        "    from pydantic import BaseSettings\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    validation_traceback = (
        "tests/test_other.py:1: in <module>\n"
        "    Other()\n"
        "E   pydantic_core._pydantic_core.ValidationError: 1 validation error for Other"
    )
    run = TestRun(
        outcomes=(
            TestOutcome("t.py::test_import", "failed", 0.1, "boom", import_traceback, None),
            TestOutcome("t.py::test_validation", "failed", 0.1, "boom", validation_traceback, None),
        ),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    sandbox = FakeSandbox(responses=[run, _passed_run()])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text='File: app/models.py\n```python\nx = 1  # "fixed"\n```\n',
                usd_cost=0.01,
                tokens_in=10,
                tokens_out=10,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    graph.invoke(state)

    assert len(fake_model.calls) == 1
    _system, prompt = fake_model.calls[0]
    assert "PydanticImportError" in prompt
    assert "ValidationError" not in prompt


def test_repair_falls_through_to_the_next_priority_diagnosis_when_the_top_one_has_no_target(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D50: found live on a real corpus repo — an import_error whose
    # ONLY first-party traceback frame is a test file itself (extract_target_file
    # correctly refuses to point at it, per I1) must not make repair() give up entirely
    # when a lower-priority diagnosis (validation_behaviour) points at a real, fixable
    # source file.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    import_traceback_test_file_only = (
        "tests/test_control.py:25: in <module>\n"
        "    class Dummy(config: pydantic.BaseSettings=None):\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    validation_traceback = (
        "app/models.py:1: in <module>\n"
        "    Other()\n"
        "E   pydantic_core._pydantic_core.ValidationError: 1 validation error for Other"
    )
    run = TestRun(
        outcomes=(
            TestOutcome(
                "t.py::test_import", "failed", 0.1, "boom", import_traceback_test_file_only, None
            ),
            TestOutcome("t.py::test_validation", "failed", 0.1, "boom", validation_traceback, None),
        ),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    sandbox = FakeSandbox(responses=[run, _passed_run()])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/models.py\n```python\nx = 2\n```\n",
                usd_cost=0.01,
                tokens_in=10,
                tokens_out=10,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)

    # fell through past the target-less import_error diagnosis and repaired using the
    # validation_behaviour one instead of giving up with repair_no_target
    assert len(fake_model.calls) == 1
    _system, prompt = fake_model.calls[0]
    assert "ValidationError" in prompt
    assert result["status"] == "done"


def test_use_triage_false_still_attempts_repair_on_an_all_preexisting_failure(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D40: use_triage=False reproduces the pre-D37 "Phase 3" shape —
    # the eval harness's ablation arm for measuring triage's actual lift needs this skip
    # to be OFF, or the comparison isn't measuring what D36/D37 added.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # nothing for T1 to fix
    sandbox = FakeSandbox(responses=[_failed_run(node_id="tests/test_x.py::test_preexisting")])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/models.py\n```python\nx = 1\n```\n",
                usd_cost=0.01,
                tokens_in=5,
                tokens_out=5,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
        use_triage=False,
    )
    baseline = BaselineResult(
        passed=frozenset(),
        failed=frozenset({"tests/test_x.py::test_preexisting"}),
        skipped=frozenset(),
        flaky=frozenset(),
        duration_s=1.0,
    )
    state = AgentState(repo=_repo(baseline=baseline), work_list=[[_unit()]])

    graph.invoke(state)

    assert len(fake_model.calls) == 1  # repair WAS attempted, unlike the use_triage=True case


def test_use_triage_false_sends_every_failure_text_not_just_one_class(tmp_path: Path) -> None:
    # the mirror of test_repair_only_sends_the_model_the_chosen_diagnosis_failure_text:
    # with triage disabled, BOTH failures' text must reach the model, matching the old
    # (pre-D38) collect_failure_texts behavior exactly.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    import_traceback = (
        "app/models.py:1: in <module>\n"
        "    from pydantic import BaseSettings\n"
        "E   pydantic.errors.PydanticImportError: `BaseSettings` has been moved"
    )
    validation_traceback = (
        "tests/test_other.py:1: in <module>\n"
        "    Other()\n"
        "E   pydantic_core._pydantic_core.ValidationError: 1 validation error for Other"
    )
    run = TestRun(
        outcomes=(
            TestOutcome("t.py::test_import", "failed", 0.1, "boom", import_traceback, None),
            TestOutcome("t.py::test_validation", "failed", 0.1, "boom", validation_traceback, None),
        ),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    sandbox = FakeSandbox(responses=[run, _passed_run()])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text='File: app/models.py\n```python\nx = 1  # "fixed"\n```\n',
                usd_cost=0.01,
                tokens_in=10,
                tokens_out=10,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
        use_triage=False,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    graph.invoke(state)

    assert len(fake_model.calls) == 1
    _system, prompt = fake_model.calls[0]
    assert "PydanticImportError" in prompt
    assert "ValidationError" in prompt  # BOTH present — no per-class filtering


def test_cumulative_outcomes_carries_forward_a_test_not_covered_by_a_later_narrow_run(
    tmp_path: Path,
) -> None:
    # docs/decisions.md D46: the real bug found on a live corpus run — run_tests_node's
    # `selection` optimization means the SECOND (and every later) test run only re-tests
    # previously-failing node_ids, so a real DockerSandbox's second TestRun would contain
    # ONLY test_b's outcome, not test_a's. cumulative_outcomes must still report test_a as
    # passing, carried forward from iteration 1, even though iteration 2 never re-tested it.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")
    traceback = "app/models.py:1: in <module>\nE   AssertionError: boom"
    iteration_1 = TestRun(
        outcomes=(
            TestOutcome("t.py::test_a", "passed", 0.1, None, None, None),
            TestOutcome("t.py::test_b", "failed", 0.1, "boom", traceback, None),
        ),
        collection_errors=(),
        exit_code=1,
        duration_s=0.1,
        truncated=False,
    )
    # simulates a real selection-narrowed run: only test_b (the one that was failing)
    # appears at all in iteration 2's outcomes.
    iteration_2 = TestRun(
        outcomes=(TestOutcome("t.py::test_b", "passed", 0.1, None, None, None),),
        collection_errors=(),
        exit_code=0,
        duration_s=0.1,
        truncated=False,
    )
    sandbox = FakeSandbox(responses=[iteration_1, iteration_2])
    fake_model = FakeModelClient(
        responses=[
            ModelResponse(
                text="File: app/models.py\n```python\nx = 2\n```\n",
                usd_cost=0.01,
                tokens_in=5,
                tokens_out=5,
            )
        ]
    )
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    state = AgentState(repo=_repo(), work_list=[[_unit()]])

    result = graph.invoke(state)

    cumulative = result["cumulative_outcomes"]
    assert cumulative["t.py::test_a"].status == "passed"  # carried forward, never re-tested
    assert cumulative["t.py::test_b"].status == "passed"  # updated by iteration 2
    assert result["status"] == "done"


def test_preexisting_failure_finalizes_without_attempting_repair(tmp_path: Path) -> None:
    # docs/decisions.md D36: the actual new capability triage wiring adds. A raw failure
    # existing doesn't mean there's real work left — if it already failed at the v1
    # baseline too, I4 says it was never a valid part of the scoring denominator, and no
    # source rewrite the agent could make would un-break something that was already
    # broken before migration started. Before this, a model_client being set meant
    # repair() would genuinely be called (and spend real money) on exactly this case.
    source_root, overlay_root = _setup_source(tmp_path, content="x = 1\n")  # nothing for T1 to fix
    sandbox = FakeSandbox(responses=[_failed_run(node_id="tests/test_x.py::test_preexisting")])
    fake_model = FakeModelClient(responses=[])  # no scripted response — raises if ever called
    graph = build_migration_graph(
        sandbox=sandbox,
        image=_image(),
        source_root=source_root,
        overlay_root=overlay_root,
        policy=SandboxPolicy(),
        model_client=fake_model,
    )
    baseline = BaselineResult(
        passed=frozenset(),
        failed=frozenset({"tests/test_x.py::test_preexisting"}),
        skipped=frozenset(),
        flaky=frozenset(),
        duration_s=1.0,
    )
    state = AgentState(repo=_repo(baseline=baseline), work_list=[[_unit()]])

    result = graph.invoke(state)

    assert result["status"] == "done"
    assert fake_model.calls == []  # repair() was never even attempted
    assert len(sandbox.run_calls) == 1  # a single test run, not a repair-and-retest loop
