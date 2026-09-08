import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from pmigrate.agent.model_client import GeminiModelClient, GroqModelClient
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.run import _build_model_client, _split_suffix, main

runner = CliRunner()
app = typer.Typer()
app.command()(main)


def _config(**overrides: object) -> EvalConfig:
    kwargs: dict[str, object] = {"name": "graph", "model": "gemini-3.6-flash"}
    kwargs.update(overrides)
    return EvalConfig(**kwargs)  # type: ignore[arg-type]


def test_build_model_client_returns_none_for_a_t1_only_config() -> None:
    config = _config(tiers=frozenset({"T1"}))
    assert _build_model_client(config) is None


def test_build_model_client_builds_gemini_for_the_known_gemini_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    config = _config(model="gemini-3.6-flash")
    client = _build_model_client(config)
    assert isinstance(client, GeminiModelClient)
    assert client.model == "gemini-3.6-flash"


def test_build_model_client_builds_groq_for_the_known_groq_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    config = _config(model="openai/gpt-oss-120b")
    client = _build_model_client(config)
    assert isinstance(client, GroqModelClient)
    assert client.model == "openai/gpt-oss-120b"


def test_build_model_client_raises_for_an_unknown_model() -> None:
    config = _config(model="claude-opus-5")
    with pytest.raises(ValueError, match="no ModelClient wired up"):
        _build_model_client(config)


def test_main_exits_with_code_1_for_a_missing_config(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    result = runner.invoke(app, ["--config", "does_not_exist", "--configs-dir", str(configs_dir)])

    assert result.exit_code == 1
    assert "no config at" in result.output


def test_main_lists_available_configs_when_one_is_missing(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(app, ["--config", "typo", "--configs-dir", str(configs_dir)])

    assert result.exit_code == 1
    assert "graph" in result.output


def test_main_rejects_an_invalid_split(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app, ["--config", "graph", "--split", "prod", "--configs-dir", str(configs_dir)]
    )

    assert result.exit_code != 0


def test_main_rejects_a_sub_one_max_workers(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app,
        [
            "--config",
            "graph",
            "--max-workers",
            "0",
            "--configs-dir",
            str(configs_dir),
        ],
    )

    assert result.exit_code != 0


def test_main_exits_with_code_1_when_docker_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))
    monkeypatch.setattr("pmigrate.eval.run.shutil.which", lambda _cmd: None)

    result = runner.invoke(app, ["--config", "graph", "--configs-dir", str(configs_dir)])

    assert result.exit_code == 1
    assert "docker not found" in result.output


def test_main_rejects_a_non_integer_seeds_list(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app, ["--config", "graph", "--seeds", "0,abc", "--configs-dir", str(configs_dir)]
    )

    assert result.exit_code != 0


def test_main_rejects_an_empty_seeds_list(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app, ["--config", "graph", "--seeds", " , ", "--configs-dir", str(configs_dir)]
    )

    assert result.exit_code != 0


def test_main_rejects_duplicate_seeds(tmp_path: Path) -> None:
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app, ["--config", "graph", "--seeds", "0,1,0", "--configs-dir", str(configs_dir)]
    )

    assert result.exit_code != 0


def test_every_shipped_config_loads_as_a_valid_eval_config() -> None:
    # configs/*.json (docs/decisions.md D64) must actually parse -- a typo here would
    # only be caught by a live `make eval` run otherwise.
    configs_dir = Path(__file__).resolve().parents[2] / "configs"
    config_paths = sorted(configs_dir.glob("*.json"))
    # Bump this deliberately when adding an arm — it exists to catch a config file going
    # MISSING, not to be kept in sync silently.
    assert len(config_paths) == 7

    for path in config_paths:
        config = EvalConfig.from_dict(json.loads(path.read_text()))
        assert config.name == path.stem


def test_split_suffix_keeps_dev_bare_and_namespaces_other_splits() -> None:
    """docs/decisions.md D83, found live: a `--split test` run wrote to the same
    `graph.md` a `--split dev` run had produced and destroyed it. I5/D7 cap test-split
    runs at three ever, so a filename collision can spend a rationed measurement
    overwriting an unrelated one. `dev` stays bare so existing artifacts keep their paths."""
    assert _split_suffix("dev") == ""
    assert _split_suffix("test") == ".test"


def test_main_refuses_split_test_without_the_intent_flag(tmp_path: Path) -> None:
    """PLAN.md I5 / docs/decisions.md D7+D84: the held-out split must never be reachable
    by a stray --split test or a loop over splits."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))

    result = runner.invoke(
        app,
        [
            "--config",
            "graph",
            "--split",
            "test",
            "--configs-dir",
            str(configs_dir),
            "--test-split-run-log",
            str(tmp_path / "runs.jsonl"),
        ],
    )

    assert result.exit_code == 1
    assert "REFUSING --split test without --i-know-what-im-doing" in result.output


def test_main_refuses_split_test_once_the_i5_budget_is_exhausted(tmp_path: Path) -> None:
    """ "At most 3 times total" is worthless if nothing counts -- so this refuses rather
    than warns, even with the intent flag present."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "graph.json").write_text(json.dumps(_config().to_dict()))
    log = tmp_path / "runs.jsonl"
    log.write_text("".join(json.dumps({"config": "graph"}) + "\n" for _ in range(3)))

    result = runner.invoke(
        app,
        [
            "--config",
            "graph",
            "--split",
            "test",
            "--i-know-what-im-doing",
            "--configs-dir",
            str(configs_dir),
            "--test-split-run-log",
            str(log),
        ],
    )

    assert result.exit_code == 1
    assert "budget is exhausted" in result.output


def test_dev_split_is_unaffected_by_the_i5_guard(tmp_path: Path) -> None:
    """The guard must not make ordinary dev runs harder. Uses a missing config so the
    command still exits early -- invoking a VALID dev config here would run the real
    corpus against Docker and hang, which is why the other tests in this file also assert
    against early-exit paths only."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()

    result = runner.invoke(app, ["--config", "absent", "--configs-dir", str(configs_dir)])

    assert result.exit_code == 1
    assert "no config at" in result.output  # got past the I5 gate to normal validation
    assert "REFUSING --split test" not in result.output
