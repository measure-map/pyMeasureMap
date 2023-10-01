"""
    Dummy conftest.py for pymeasuremap.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""
import os.path
from functools import cache
from pathlib import Path
from typing import Dict

import pytest
from git import Repo

from pymeasuremap.utils import collect_measure_maps

REPOSITORY_PATH = "~"
"""Path where the clones of the following repositories are located:
- https://github.com/measure-map/aligned_bach_chorales
"""

# setup paths
REPOSITORY_PATH = Path(REPOSITORY_PATH).expanduser()
assert (
    REPOSITORY_PATH.is_dir()
), f"REPOSITORY_PATH is not set to an existing directory: {REPOSITORY_PATH}"


@cache
def get_mm_path_dict() -> Dict[str, Path]:
    """Create file with paths to all measure maps in the aligned_bach_chorales repository before setting up fixtures."""
    aligned_bach_chorales_path = get_aligned_bach_chorales_path()
    path_dict = {}
    for filepath in collect_measure_maps(aligned_bach_chorales_path):
        fname, _ = os.path.splitext(os.path.basename(filepath))
        path_dict[fname] = Path(filepath)
    return path_dict


def get_aligned_bach_chorales_path() -> Path:
    p = REPOSITORY_PATH / "aligned_bach_chorales"
    if not p.is_dir():
        Repo.clone_from(
            "https://github.com/measure-map/aligned_bach_chorales", p, depth=1
        )
    return p


def get_mm_paths_params():
    """Used to parametrize tests."""
    return list(get_mm_path_dict().values())


def get_mm_paths_ids():
    """Used to parametrize tests."""
    return list(get_mm_path_dict().keys())


@pytest.fixture(scope="session", params=get_mm_paths_params(), ids=get_mm_paths_ids())
def single_mm_path(request) -> Path:
    return request.param
