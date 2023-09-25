from pymeasuremap.base import MeasureMap
from pymeasuremap.utils import collect_measure_maps


def test_compression(aligned_bach_chorales_path):
    print(aligned_bach_chorales_path)
    mm_paths = collect_measure_maps(aligned_bach_chorales_path)
    for mm_path in mm_paths:
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
