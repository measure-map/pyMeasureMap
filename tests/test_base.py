from difflib import unified_diff

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
