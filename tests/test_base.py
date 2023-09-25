from difflib import unified_diff

from pymeasuremap.base import MeasureMap


def test_compression(all_bach_mm_paths):
    for mm_path in all_bach_mm_paths:
        print("\n", mm_path)
        MM = MeasureMap.from_json_file(mm_path)
        # prototype of compression algorithm:
        previous_measure = None
        for measure in MM:
            if previous_measure is None:
                previous_measure = measure
                continue
            default_successor = previous_measure.get_default_successor()
            if measure == default_successor:
                print(f"MC {measure.count} can be re-generated from its predecessor.")
            else:
                print(
                    f"MC {measure.count} cannot be re-generated from its predecessor.\n"
                    f"Displaying (predecessor MC {previous_measure.count}, default successor, actual successor MC"
                    f" {measure.count}):"
                    f"\n\t{previous_measure}\n\t{default_successor}\n\t{measure}"
                )
            previous_measure = measure


def test_json_output(single_mm_path, tmp_path):
    mm = MeasureMap.from_json_file(single_mm_path)
    tmp_filepath = tmp_path / "temp.mm.json"
    mm.to_json_file(tmp_filepath)
    with open(single_mm_path, "r") as f1, open(tmp_filepath, "r") as f2:
        text1_lines, text2_lines = f1.readlines(), f2.readlines()
        diff = unified_diff(text1_lines, text2_lines, lineterm="")
        diff_str = "\n".join(diff)
        print(
            f"Comparing original {single_mm_path} with {tmp_filepath}:\n\n{diff_str}..."
        )
        assert diff_str == ""
