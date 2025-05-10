import logging
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from pymeasuremap.base import MeasureMap
from pymeasuremap.utils import apply_function_to_directory, load_tsv

module_logger = logging.getLogger(__name__)


def measures_df2measure_map(measures_df: pd.DataFrame) -> MeasureMap:
    """Turns the given measures table into a table corresponding to the MeasureMap specification. This includes
    renaming columns and applying mild transformations to some of them. The resulting measure map can be converted
    to JSON format via ``df.to_json(orient='records')``.

    Args:
        measures_df: Measures table for a single piece.

    Returns:
        The measure map where each row corresponds to one entry.

    Raises:
        ValueError:
            If there are NA values in the quarterbeats column. If a quarterbeats_all_endings column is present,
            which should never include NA values, it will be used for the "qstamp" column.
    """
    # renaming columns
    count_col = measures_df.mc
    id_col = count_col.astype(str)
    number_col = measures_df.mn
    name_col = number_col.astype(str)
    if "volta" in measures_df:

        def make_repeat_char(val: int) -> str:
            """Turns a volta number into the corresponding repeat character."""
            if pd.isnull(val):
                return ""
            try:
                return chr(int(val) + 96)  # 1 -> 'a', 2 -> 'b', etc.
            except Exception:
                return ""

        name_col += measures_df.volta.map(make_repeat_char)
    name_col = name_col
    timesig_col = measures_df["timesig"]

    # quarterbeats_all_endings only present in measures if score has voltas
    if "quarterbeats_all_endings" in measures_df:
        qstamp_col = measures_df["quarterbeats_all_endings"]
    else:
        qstamp_col = measures_df["quarterbeats"]
    if qstamp_col.isna().any():
        raise ValueError(f"There are NA values in the column {qstamp_col.name!r}.")
    qstamp_col = qstamp_col.astype(float)
    nominal_col = measures_df.timesig.map(Fraction) * 4.0
    actual_col = measures_df.act_dur * 4.0
    start_repeat_col = measures_df.repeats.str.contains("start").fillna(False)
    end_repeat_col = measures_df.repeats.str.contains("end").fillna(False)
    next_col = measures_df.next.map(list)

    return MeasureMap.from_array(
        ID=id_col.values,
        count=count_col.values,
        qstamp=qstamp_col.values,
        number=number_col.values,
        name=name_col.values,
        time_signature=timesig_col.values,
        nominal_length=nominal_col.values,
        actual_length=actual_col.values,
        start_repeat=start_repeat_col.values,
        end_repeat=end_repeat_col.values,
        next=next_col.values,
    )


def measures_tsv_filepath_to_measure_map(
    source_tsv_filepath: Path | str,
):
    try:
        measures_df = load_tsv(source_tsv_filepath)
    except (ValueError, AssertionError) as e:
        raise ValueError(
            f"{source_tsv_filepath} could not be loaded because of the following error:\n'{e}'"
        )
    return measures_df2measure_map(measures_df)


def convert_directory(
    directory: Path | str,
    output_directory: Optional[Path | str] = None,
    file_regex: str = "*",
    extensions: Optional[str | Iterable[str]] = None,
    measure_map_extension: str = ".mm.json",
):
    return apply_function_to_directory(
        func=measures_tsv_filepath_to_measure_map,
        directory=directory,
        output_directory=output_directory,
        file_regex=file_regex,
        extensions=extensions,
        measure_map_extension=measure_map_extension,
    )
