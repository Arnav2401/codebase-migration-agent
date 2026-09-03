import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from pmigrate.triage.label import LabelledFailure, load_labelled, main
from pmigrate.types import FailureClass

runner = CliRunner()
app = typer.Typer()
app.command()(main)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def _raw(repo_id: str, node_id: str, predicted_cls: str, text: str) -> dict:
    return {"repo_id": repo_id, "node_id": node_id, "predicted_cls": predicted_cls, "text": text}


def test_groups_failures_sharing_class_and_root_frame(tmp_path: Path) -> None:
    # two failures with the SAME predicted class and the SAME first-party frame must be
    # one group (a single question), not two -- the entire point of grouping before asking.
    shared_text = "app/settings.py:1: in <module>\nE   pydantic.errors.PydanticImportError: x"
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    _write_jsonl(
        failures_in,
        [
            _raw("acme__widgets", "t.py::a", "import_error", shared_text),
            _raw("acme__widgets", "t.py::b", "import_error", shared_text),
        ],
    )

    result = runner.invoke(
        app,
        ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)],
        input="import_error\n",
    )

    assert result.exit_code == 0
    assert "1 of 1 groups" in result.output
    labelled = load_labelled(labelled_out)
    assert len(labelled) == 2
    assert all(lf.true_cls == FailureClass.IMPORT_ERROR for lf in labelled)


def test_different_root_frame_stays_a_separate_group(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    _write_jsonl(
        failures_in,
        [
            _raw(
                "acme__widgets",
                "t.py::a",
                "import_error",
                "app/a.py:1: in x\nE   PydanticImportError",
            ),
            _raw(
                "acme__widgets",
                "t.py::b",
                "import_error",
                "app/b.py:1: in y\nE   PydanticImportError",
            ),
        ],
    )

    result = runner.invoke(
        app,
        ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)],
        input="import_error\nremoved_api\n",
    )

    assert result.exit_code == 0
    assert "2 of 2 groups" in result.output
    labelled = {lf.node_id: lf.true_cls for lf in load_labelled(labelled_out)}
    assert labelled["t.py::a"] == FailureClass.IMPORT_ERROR
    assert labelled["t.py::b"] == FailureClass.REMOVED_API


def test_rejects_an_invalid_class_and_reprompts(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    _write_jsonl(failures_in, [_raw("acme__widgets", "t.py::a", "unknown", "E   AssertionError")])

    result = runner.invoke(
        app,
        ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)],
        input="not_a_real_class\nunknown\n",
    )

    assert result.exit_code == 0
    assert "Not a valid class" in result.output
    assert load_labelled(labelled_out)[0].true_cls == FailureClass.UNKNOWN


def test_s_cycles_through_samples_without_answering(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    shared_text = "app/x.py:1: in <module>\nE   PydanticImportError"
    _write_jsonl(
        failures_in,
        [
            _raw("acme__widgets", "t.py::a", "import_error", shared_text),
            _raw("acme__widgets", "t.py::b", "import_error", shared_text),
        ],
    )

    result = runner.invoke(
        app,
        ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)],
        input="s\nimport_error\n",
    )

    assert result.exit_code == 0
    assert "sample 2/2" in result.output
    assert len(load_labelled(labelled_out)) == 2


def test_q_quits_without_writing_the_current_group(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    _write_jsonl(
        failures_in,
        [
            _raw(
                "acme__widgets",
                "t.py::a",
                "import_error",
                "app/a.py:1: in x\nE   PydanticImportError",
            ),
            _raw(
                "acme__widgets",
                "t.py::b",
                "import_error",
                "app/b.py:1: in y\nE   PydanticImportError",
            ),
        ],
    )

    result = runner.invoke(
        app, ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)], input="q\n"
    )

    assert result.exit_code == 0
    # quit on the FIRST group without answering -- both groups (including the one just
    # shown) are still unlabelled.
    assert "2 group(s) still need labelling" in result.output
    assert not labelled_out.exists() or load_labelled(labelled_out) == []


def test_resuming_skips_already_labelled_groups(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    already = LabelledFailure(
        repo_id="acme__widgets",
        node_id="t.py::a",
        predicted_cls=FailureClass.IMPORT_ERROR,
        true_cls=FailureClass.IMPORT_ERROR,
        text="app/a.py:1: in x\nE   PydanticImportError",
    )
    _write_jsonl(
        labelled_out,
        [
            {
                "repo_id": already.repo_id,
                "node_id": already.node_id,
                "predicted_cls": already.predicted_cls.value,
                "true_cls": already.true_cls.value,
                "text": already.text,
            }
        ],
    )
    _write_jsonl(
        failures_in,
        [
            _raw("acme__widgets", "t.py::a", "import_error", already.text),  # already labelled
            _raw("acme__widgets", "t.py::b", "unknown", "E   AssertionError"),  # still pending
        ],
    )

    result = runner.invoke(
        app,
        ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)],
        input="unknown\n",
    )

    assert result.exit_code == 0
    assert "1 of 2 groups" in result.output
    labelled = load_labelled(labelled_out)
    assert len(labelled) == 2  # the pre-existing one plus the newly-labelled one
    assert {lf.node_id for lf in labelled} == {"t.py::a", "t.py::b"}


def test_exits_cleanly_when_all_groups_already_labelled(tmp_path: Path) -> None:
    failures_in = tmp_path / "failures.jsonl"
    labelled_out = tmp_path / "labelled.jsonl"
    text = "app/a.py:1: in x\nE   PydanticImportError"
    _write_jsonl(failures_in, [_raw("acme__widgets", "t.py::a", "import_error", text)])
    _write_jsonl(
        labelled_out,
        [
            {
                "repo_id": "acme__widgets",
                "node_id": "t.py::a",
                "predicted_cls": "import_error",
                "true_cls": "import_error",
                "text": text,
            }
        ],
    )

    result = runner.invoke(
        app, ["--failures-in", str(failures_in), "--labelled-out", str(labelled_out)]
    )

    assert result.exit_code == 0
    assert "already labelled" in result.output


def test_exits_with_an_error_when_there_is_no_failures_file(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--failures-in",
            str(tmp_path / "missing.jsonl"),
            "--labelled-out",
            str(tmp_path / "out.jsonl"),
        ],
    )
    assert result.exit_code == 1
