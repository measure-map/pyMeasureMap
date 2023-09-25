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
from typing import List

import pytest

from pymeasuremap.utils import collect_measure_maps

REPOSITORY_PATH = "~/git"
"""Path where the clones of the following repositories are located:
- https://github.com/measure-map/aligned_bach_chorales
"""


def get_mm_paths_filepath() -> Path:
    """An arbitrary filepath where a text files containing the paths of the individual test files is stored."""
    return Path(__file__).parent / "all_bach_mm_paths.txt"


@cache
def mm_paths_dict() -> dict[str, Path]:
    """Returns a dictionary mapping the name of the measure map to the path of the file containing it."""
    mm_paths_file = get_mm_paths_filepath()
    path_dict = {}
    with open(mm_paths_file, "r", encoding="utf-8") as f:
        for line in f:
            filepath = line.strip()
            fname, _ = os.path.splitext(os.path.basename(filepath))
            path_dict[fname] = Path(filepath)
    return path_dict


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


@pytest.fixture(scope="session", autouse=True)
def create_mm_paths_file(aligned_bach_chorales_path) -> List[str]:
    """Collects the paths and writes them to a file while setting up the session so that the paths can be used to
    parameterize tests."""
    mm_paths = collect_measure_maps(aligned_bach_chorales_path)
    mm_paths_file = get_mm_paths_filepath()
    with open(mm_paths_file, "w", encoding="utf-8") as f:
        f.write("\n".join(mm_paths))
    yield


@pytest.fixture(
    scope="session", params=mm_paths_dict().values(), ids=mm_paths_dict().keys()
)
def single_mm_path(request) -> Path:
    return request.param
