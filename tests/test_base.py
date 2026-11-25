from difflib import unified_diff

import pytest

from pymeasuremap.base import MeasureMap


def test_compression(single_mm_path):
    MM = MeasureMap.from_json_file(single_mm_path)
    compressed = MM.compress()
    assert len(compressed.entries) < len(MM.entries)


def test_decompression(single_mm_path):
    MM = MeasureMap.from_json_file(single_mm_path)
    assert MM.compress().decompress() == MM


def test_decompression_of_trailing_entries():
    MM = MeasureMap.from_array(count=[1, 2, 3], time_signature=["4/4"] * 3)
    assert len(MM.compress().entries) == 2
    assert MM.compress().decompress() == MM


def test_decompression_without_time_signature():
    MM = MeasureMap.from_array(count=[1, 2, 3], actual_length=[2.0] * 3)
    assert MM.compress().decompress() == MM


def test_volta():
    MM = MeasureMap.from_array(count=[1, 2, 3, 4], volta=[None, 1, 1, 2])
    assert MM.compress().decompress() == MM
    assert MM.to_dicts()[1] == {"count": 2, "volta": 1}
    with pytest.raises(AssertionError):
        MeasureMap.from_array(count=[1, 2], volta=[0, 1])


def test_volta_with_several_numbers(tmp_path):
    """An ending that is played in several passes ('1.-2.', or first and third time) lists their numbers. The list
    has to survive what every other value survives: writing and reading the JSON file, and compression.
    """
    MM = MeasureMap.from_array(
        count=[1, 2, 3, 4, 5], volta=[None, [1, 2], [1, 2], 3, None]
    )
    assert [measure.volta for measure in MM] == [None, [1, 2], [1, 2], 3, None]
    assert MM.to_dicts()[1] == {"count": 2, "volta": [1, 2]}
    assert MM.to_dicts()[3] == {"count": 4, "volta": 3}
    filepath = tmp_path / "voltas.mm.json"
    MM.to_json_file(filepath)
    assert MeasureMap.from_json_file(filepath) == MM
    # counts 2 and 3 share an ending, so the second one is the default successor of the first and can be omitted
    compressed = MM.compress()
    assert [measure.count for measure in compressed] == [1, 2, 4, 5]
    assert compressed.decompress() == MM


def test_volta_numbers():
    """get_volta_numbers() gives the passes of a measure in one form, whichever way 'volta' was written. A list of
    one number is kept as it was written."""
    MM = MeasureMap.from_array(count=[1, 2, 3, 4], volta=[None, 2, [1, 3], [2]])
    assert [measure.get_volta_numbers() for measure in MM] == [(), (2,), (1, 3), (2,)]
    assert MM.to_dicts()[3] == {"count": 4, "volta": [2]}


@pytest.mark.parametrize("volta", [[], [1, 0], [2, 2], [-1], 0])
def test_invalid_volta(volta):
    """Passes are counted from 1, an ending belongs to at least one pass and to none twice."""
    with pytest.raises(AssertionError, match="volta must be a positive integer"):
        MeasureMap.from_array(count=[1, 2], volta=[None, volta])


def test_json_output(single_mm_path, tmp_path):
    mm = MeasureMap.from_json_file(single_mm_path)
    tmp_filepath = tmp_path / "temp.mm.json"
    mm.to_json_file(tmp_filepath)
    with open(single_mm_path, "r") as f1, open(tmp_filepath, "r") as f2:
        text1_lines, text2_lines = f1.readlines(), f2.readlines()
        diff = unified_diff(text1_lines, text2_lines, lineterm="")
        diff_str = "".join(diff)
        print(
            f"Comparing original {single_mm_path} with {tmp_filepath}:\n\n{diff_str}..."
        )
        assert diff_str == ""


def test_json_output_to_bare_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mm = MeasureMap.from_array(count=[1, 2], time_signature=["4/4"] * 2)
    mm.to_json_file("temp.mm.json")
    assert MeasureMap.from_json_file("temp.mm.json") == mm
