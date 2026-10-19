import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from abusecheck import policy as policy_mod  # noqa: E402
from abusecheck import world as world_mod  # noqa: E402


@pytest.fixture
def root():
    return ROOT


@pytest.fixture
def world():
    return world_mod.load(ROOT / "world.toml")


@pytest.fixture
def policy():
    return policy_mod.load(ROOT / "policy.toml")
