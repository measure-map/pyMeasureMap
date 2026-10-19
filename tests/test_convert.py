from fractions import Fraction

import pandas as pd

from pymeasuremap.convert import measures_df2measure_map


def test_volta_conversion():
    measures_df = pd.DataFrame(
        {
            "mc": [1, 2, 3],
            "mn": [1, 2, 2],
            "timesig": ["2/4"] * 3,
            "quarterbeats": [0.0, 2.0, 2.0],
            "act_dur": [Fraction(1, 2)] * 3,
            "repeats": [None, "end", None],
            "next": [(2,), (1, 3), ()],
            "volta": pd.Series([pd.NA, 1, 2], dtype="Int64"),
        }
    )
    mm = measures_df2measure_map(measures_df)
    assert [measure.volta for measure in mm] == [None, 1, 2]
    assert [measure.name for measure in mm] == ["1", "2a", "2b"]
