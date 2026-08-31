from pmigrate.graph.relevance import (
    compute_work_list,
    find_pydantic_model_classes,
    import_edges_touching,
)
from pmigrate.graph.resolver import resolve_repo


def test_transitive_basemodel_detection_direct_and_inherited(
    sample_repo_files: dict[str, bytes],
) -> None:
    resolved = resolve_repo(sample_repo_files)
    model_classes = find_pydantic_model_classes(resolved)
    assert model_classes[("app.models.user", "User")] == "BaseModel"


def test_work_list_flags_user_module_and_orders_leaves_first(
    sample_repo_files: dict[str, bytes],
) -> None:
    resolved = resolve_repo(sample_repo_files)
    batches = compute_work_list(resolved, repo_id="sample")
    flagged_modules = {unit.module for batch in batches for unit in batch}
    assert "app.models.user" in flagged_modules

    unit = next(u for batch in batches for u in batch if u.module == "app.models.user")
    assert "BaseModel" in unit.signals
    assert unit.est_difficulty >= 1
    assert len(unit.symbols) == 1
    assert unit.symbols[0].fqname == "app.models.user.User"


def test_work_list_is_leaf_first_relative_to_import_order(
    sample_repo_files: dict[str, bytes],
) -> None:
    resolved = resolve_repo(sample_repo_files)
    batches = compute_work_list(resolved, repo_id="sample")
    module_batch_index = {}
    for i, batch in enumerate(batches):
        for unit in batch:
            module_batch_index[unit.module] = i

    # app.models.user is imported (transitively) by app, app.models, app.api.routes,
    # app.api — none of those should be able to appear before it.
    if "app" in module_batch_index:
        assert module_batch_index["app.models.user"] <= module_batch_index["app"]


def test_synthetic_repo_transitive_subclass_two_hops() -> None:
    files = {
        "base.py": b"from pydantic import BaseModel\n\nclass Intermediate(BaseModel):\n    pass\n",
        "leaf.py": b"from base import Intermediate\n\nclass Leaf(Intermediate):\n    x: int = 1\n",
    }
    resolved = resolve_repo(files)
    model_classes = find_pydantic_model_classes(resolved)
    assert model_classes[("base", "Intermediate")] == "BaseModel"
    assert model_classes[("leaf", "Leaf")] == "BaseModel"


def test_field_v1_kwargs_and_config_and_validator_signals_detected() -> None:
    files = {
        "m.py": (
            b"from pydantic import BaseModel, validator\n\n"
            b"class M(BaseModel):\n"
            b"    name: str = Field(regex='^a')\n\n"
            b"    class Config:\n"
            b"        orm_mode = True\n\n"
            b"    @validator('name')\n"
            b"    def check(cls, v):\n"
            b"        return v\n"
        )
    }
    resolved = resolve_repo(files)
    batches = compute_work_list(resolved, repo_id="sample")
    unit = batches[0][0]
    assert unit.signals >= {"BaseModel", "Config", "validator", "field_v1_kwargs"}
    assert unit.est_difficulty == 2


def test_non_model_class_is_not_flagged() -> None:
    files = {"m.py": b"class Plain:\n    def f(self):\n        return 1\n"}
    resolved = resolve_repo(files)
    batches = compute_work_list(resolved, repo_id="sample")
    assert batches == []


def test_import_edges_touching_helper(sample_repo_files: dict[str, bytes]) -> None:
    resolved = resolve_repo(sample_repo_files)
    hits = import_edges_touching(resolved, "pydantic", "BaseModel")
    assert len(hits) == 1
    assert hits[0].from_module == "app.models.user"
