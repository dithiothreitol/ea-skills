import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def example_root() -> Path:
    return REPO_ROOT / "eval" / "example"


@pytest.fixture(scope="session")
def broken_root() -> Path:
    return REPO_ROOT / "eval" / "fixtures" / "broken"
