from pathlib import Path

from pmigrate.agent.retrieval import GraphRetrieval, WholefileRetrieval


def _setup_repo(tmp_path: Path) -> Path:
    app = tmp_path / "app"
    app.mkdir()
    (app / "base.py").write_text(
        "from pydantic import BaseModel\n\n\nclass BrokenBase(BaseModel):\n    val: str = None\n"
    )
    (app / "models.py").write_text(
        "from app.base import BrokenBase\n\n\nclass AppSettings(BrokenBase):\n    pass\n"
    )
    (app / "unrelated.py").write_text("x = 1\n")
    return tmp_path


def test_graph_retrieval_finds_an_imported_base_class_file(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    retrieval = GraphRetrieval(repo_id="acme__widgets")

    related = retrieval.related_files("app/models.py", target_before, root)

    assert related == ("app/base.py",)


def test_graph_retrieval_excludes_the_target_itself(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    retrieval = GraphRetrieval(repo_id="acme__widgets")

    related = retrieval.related_files("app/models.py", target_before, root)

    assert "app/models.py" not in related


def test_graph_retrieval_returns_empty_for_an_unknown_target_path(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    retrieval = GraphRetrieval(repo_id="acme__widgets")

    assert retrieval.related_files("app/does_not_exist.py", "", root) == ()


def test_wholefile_retrieval_returns_every_pydantic_touching_file_except_target(
    tmp_path: Path,
) -> None:
    root = _setup_repo(tmp_path)
    target_before = (root / "app" / "models.py").read_text()
    retrieval = WholefileRetrieval()

    related = retrieval.related_files("app/models.py", target_before, root)

    # base.py defines a real pydantic model; unrelated.py has none, so it's excluded --
    # matching graph/relevance.py's own signal, not a separate heuristic.
    assert related == ("app/base.py",)


def test_wholefile_retrieval_respects_a_tiny_token_budget(tmp_path: Path) -> None:
    root = _setup_repo(tmp_path)
    # a second pydantic-touching file so there's something a tiny budget can exclude
    (root / "app" / "extra_model.py").write_text(
        "from pydantic import BaseModel\n\n\nclass Extra(BaseModel):\n    x: int\n"
    )
    target_before = (root / "app" / "models.py").read_text()
    retrieval = WholefileRetrieval(budget_tokens=1)  # smaller than even one file's cost

    related = retrieval.related_files("app/models.py", target_before, root)

    # truncate_to_budget always keeps at least the first candidate even over budget, but
    # never a second one once the budget is already exceeded.
    assert len(related) <= 1
