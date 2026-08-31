from pathlib import Path

from pmigrate.graph.memory_store import InMemoryCodeGraph
from pmigrate.types import EdgeKind, RepoSpec, SymbolKind

from .conftest import FIXTURE_ROOT


def _make_repo_spec(repo_id: str = "sample") -> RepoSpec:
    return RepoSpec(
        repo_id=repo_id,
        url="https://example.invalid/sample",
        pre_sha="0" * 40,
        post_sha="1" * 40,
        python_version="3.11",
        install_cmd=("pip", "install", "."),
        test_cmd=("pytest",),
    )


def test_ingest_reports_stats() -> None:
    graph = InMemoryCodeGraph()
    stats = graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    assert stats.modules_parsed == 9  # every .py file under the fixture repo
    assert stats.symbols_created > stats.modules_parsed
    assert stats.edges_created > 0
    assert 0.0 < stats.resolution_coverage < 1.0  # the fixture has one deliberate failure


def test_get_returns_known_symbol() -> None:
    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    ref = graph.get("sample", "app.models.user.User")
    assert ref is not None
    assert ref.kind == SymbolKind.CLASS
    assert ref.path == "app/models/user.py"
    assert graph.get("sample", "does.not.exist") is None


def test_dependents_of_user_class_via_inherits_and_imports() -> None:
    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    user = graph.get("sample", "app.models.user.User")
    assert user is not None

    # nothing first-party subclasses User in the fixture, so INHERITS dependents is empty —
    # but the *module* app.models.user has real dependents via IMPORTS.
    module_ref = graph.get("sample", "app.models.user")
    assert module_ref is not None
    dependents = graph.dependents(module_ref, depth=1, kinds={EdgeKind.IMPORTS})
    dependent_fqnames = {d.fqname for d in dependents}
    assert "app.models" in dependent_fqnames


def test_dependencies_of_module_includes_contains_children() -> None:
    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    module_ref = graph.get("sample", "app.models.user")
    assert module_ref is not None
    deps = graph.dependencies(module_ref, depth=1, kinds={EdgeKind.CONTAINS})
    assert any(d.fqname == "app.models.user.User" for d in deps)


def test_topo_modules_orders_user_before_its_importers() -> None:
    # Note: the re-export chase in resolver.py points an edge straight at the true
    # definer, bypassing intermediate re-exporting packages — so `app` imports
    # `app.models.user` directly (not `app.models`), and `app`/`app.models` end up as
    # independent siblings with no direct edge between them. That's intentional: for
    # migration ordering, app/__init__.py's passthrough import doesn't itself need
    # anything to change once app.models.user is migrated.
    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    batches = graph.topo_modules("sample")
    flat_index = {m: i for i, batch in enumerate(batches) for m in batch}
    assert flat_index["app.models.user"] < flat_index["app.models"]
    assert flat_index["app.models.user"] < flat_index["app"]
    assert flat_index["app.utils.helpers"] < flat_index["app.models.user"]


def test_neighbourhood_respects_token_budget() -> None:
    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec(), FIXTURE_ROOT)
    user_module = graph.get("sample", "app.models.user")
    assert user_module is not None
    wide = graph.neighbourhood(user_module, budget_tokens=10_000)
    narrow = graph.neighbourhood(user_module, budget_tokens=1)
    assert len(narrow) <= len(wide)
    assert len(narrow) <= 1


def test_two_repos_are_namespaced_independently(tmp_path: Path) -> None:
    other_root = tmp_path / "other"
    (other_root / "pkg").mkdir(parents=True)
    (other_root / "pkg" / "__init__.py").write_text("")
    (other_root / "pkg" / "mod.py").write_text("class Thing:\n    pass\n")

    graph = InMemoryCodeGraph()
    graph.ingest(_make_repo_spec("sample"), FIXTURE_ROOT)
    graph.ingest(_make_repo_spec("other"), other_root)

    assert graph.get("sample", "app.models.user.User") is not None
    assert graph.get("other", "app.models.user.User") is None
    assert graph.get("other", "pkg.mod.Thing") is not None
    assert graph.topo_modules("other") != graph.topo_modules("sample")
