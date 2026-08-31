from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def load_fixture_repo(root: Path = FIXTURE_ROOT) -> dict[str, bytes]:
    files = {}
    for path in root.rglob("*.py"):
        rel = str(path.relative_to(root))
        files[rel] = path.read_bytes()
    return files


@pytest.fixture
def sample_repo_files() -> dict[str, bytes]:
    return load_fixture_repo()
