from copy import deepcopy

from pymeasuremap.base import MeasureMap
from pymeasuremap.compare import Compare, one_comparison


def make_mm(actual_lengths, **kwargs) -> MeasureMap:
    n = len(actual_lengths)
    return MeasureMap.from_array(
        count=range(1, n + 1),
        number=range(1, n + 1),
        time_signature=["4/4"] * n,
        actual_length=actual_lengths,
        **kwargs,
    )


def test_diagnose_does_not_modify_measure_maps():
    preferred = make_mm([4.0, 4.0, 4.0], start_repeat=[True, False, False])
    other = make_mm([4.0, 4.0, 3.0], start_repeat=[False] * 3)
    preferred_copy, other_copy = deepcopy(preferred), deepcopy(other)
    diagnosis = Compare(preferred, other).diagnose()
    assert diagnosis == [("Repeat_Marks", 1, "start"), ("Measure_Length", 3, 4.0)]
    assert (preferred, other) == (preferred_copy, other_copy)


def test_diagnose_join():
    diagnosis = Compare(make_mm([4.0, 4.0]), make_mm([1.0, 3.0, 4.0])).diagnose()
    assert diagnosis == [("Join", 1)]


def test_diagnose_unalignable_lengths():
    diagnosis = Compare(make_mm([4.0, 4.0]), make_mm([2.0, 1.0, 1.0])).diagnose()
    assert diagnosis[0][0] == "Needleman-Wunsch"


def test_one_comparison(tmp_path):
    preferred_path, other_path = tmp_path / "preferred.json", tmp_path / "other.json"
    make_mm([4.0, 4.0]).to_json_file(preferred_path)
    make_mm([4.0, 3.0]).to_json_file(other_path)
    assert one_comparison(preferred_path, other_path, write=False) == [
        ("Measure_Length", 2, 4.0)
    ]
