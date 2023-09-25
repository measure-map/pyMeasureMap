"""
    Dummy conftest.py for pymeasuremap.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""
from pathlib import Path
from typing import List

import pytest

from pymeasuremap.utils import collect_measure_maps

REPOSITORY_PATH = "~/git"
"""Path where the clones of the following repositories are located:
- https://github.com/measure-map/aligned_bach_chorales
"""


@pytest.fixture(scope="session")
def repository_path() -> Path:
    p = Path(REPOSITORY_PATH).expanduser()
    assert p.is_dir(), f"Repository path {p} does not exist."
    return p


@pytest.fixture(scope="session")
def aligned_bach_chorales_path(repository_path) -> Path:
    p = repository_path / "aligned_bach_chorales"
    assert p.is_dir(), f"Repository path {p} does not exist."
    return p


@pytest.fixture(scope="session")
def all_bach_mm_paths(aligned_bach_chorales_path) -> List[str]:
    return collect_measure_maps(aligned_bach_chorales_path)


@pytest.fixture(scope="session")
def single_mm_path(all_bach_mm_paths) -> Path:
    return Path(all_bach_mm_paths[0])
