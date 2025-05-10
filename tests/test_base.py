from difflib import unified_diff

from pymeasuremap.base import MeasureMap


def test_compression(single_mm_path):
    MM = MeasureMap.from_json_file(single_mm_path)
    compressed = MM.compress()
    assert len(compressed.entries) < len(MM.entries)


def test_decompression():
    mm = MeasureMap.from_dicts([{"time_signature": "2/2"}, {"number": 563}])
    print(mm[0])


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
