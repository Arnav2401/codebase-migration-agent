from pmigrate.graph.resolver import resolve_repo


def _edges_from(resolved, from_module: str) -> list:
    return [e for e in resolved.import_edges if e.from_module == from_module]


def test_absolute_third_party_import(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.models.user")
    pydantic_edges = [e for e in edges if e.to_module == "pydantic"]
    assert len(pydantic_edges) == 1
    assert pydantic_edges[0].is_first_party is False
    assert pydantic_edges[0].imported_names == ("BaseModel",)


def test_multi_level_relative_import(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.models.user")
    helper_edges = [e for e in edges if e.to_module == "app.utils.helpers"]
    assert len(helper_edges) == 1
    assert helper_edges[0].is_first_party is True
    assert helper_edges[0].imported_names == ("normalize",)


def test_init_py_reexport_resolves_to_defining_module(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    # app/__init__.py does `from .models import User` — models/__init__.py re-exports User
    # from .user — the edge should point through both hops to app.models.user, not stop
    # at the intermediate package.
    edges = _edges_from(resolved, "app")
    reexport_edges = [e for e in edges if e.to_module == "app.models.user"]
    assert len(reexport_edges) == 1

    edges2 = _edges_from(resolved, "app.models")
    reexport_edges2 = [e for e in edges2 if e.to_module == "app.models.user"]
    assert len(reexport_edges2) == 1


def test_relative_submodule_import_distinct_from_reexport(
    sample_repo_files: dict[str, bytes],
) -> None:
    # routes.py does `from . import handlers` where handlers.py is a REAL submodule,
    # as opposed to `from ..models import User` which chases a re-export.
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.api.routes")
    handler_edges = [e for e in edges if e.to_module == "app.api.handlers"]
    assert len(handler_edges) == 1
    assert handler_edges[0].imported_names == ("handlers",)

    # routes.py also has a second, TYPE_CHECKING-guarded import to the same target
    # (see test_type_checking_edge_flagged) — filter to the real one.
    user_edges = [e for e in edges if e.to_module == "app.models.user" and not e.type_only]
    assert len(user_edges) == 1
    assert user_edges[0].imported_names == ("User",)


def test_type_checking_edge_flagged(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.api.routes")
    type_only_edges = [e for e in edges if e.type_only]
    assert len(type_only_edges) == 1
    assert type_only_edges[0].to_module == "app.models.user"


def test_star_import_recorded_but_unresolved_names(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.api")
    star_edges = [e for e in edges if e.imported_names == ("*",)]
    assert len(star_edges) == 1
    assert star_edges[0].to_module == "app.api.routes"
    assert star_edges[0].is_first_party is True


def test_over_climbing_relative_import_is_unresolved(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    edges = _edges_from(resolved, "app.broken_import")
    assert edges == []  # unresolvable, correctly dropped rather than silently wrong
    assert resolved.unresolved_count >= 1


def test_resolution_coverage_is_measured_honestly(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    assert resolved.total_import_count > resolved.unresolved_count > 0
    assert 0.0 < resolved.resolution_coverage < 1.0
    # the fixture has exactly one deliberately-unresolvable import
    assert resolved.unresolved_count == 1
