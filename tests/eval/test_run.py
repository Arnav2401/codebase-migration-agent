import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from pmigrate.agent.model_client import GeminiModelClient, GroqModelClient
from pmigrate.eval.config import EvalConfig
from pmigrate.eval.run import _build_model_client, main

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


def test_every_shipped_config_loads_as_a_valid_eval_config() -> None:
    # configs/*.json (docs/decisions.md D64) must actually parse -- a typo here would
    # only be caught by a live `make eval` run otherwise.
    configs_dir = Path(__file__).resolve().parents[2] / "configs"
    config_paths = sorted(configs_dir.glob("*.json"))
    assert len(config_paths) == 7

    for path in config_paths:
        config = EvalConfig.from_dict(json.loads(path.read_text()))
        assert config.name == path.stem
