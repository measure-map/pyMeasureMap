from __future__ import annotations

import json
import logging
import os
import warnings
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Tuple, Union

import pandas as pd
from music21 import converter

if TYPE_CHECKING:
    from pymeasuremap.base import MeasureMap

module_logger = logging.getLogger(__name__)


def safe_fraction(s: str) -> Optional[Union[Fraction, str]]:
    try:
        return Fraction(s)
    except Exception:
        return


def str2inttuple(tuple_string: str, strict: bool = True) -> Tuple[int]:
    tuple_string = tuple_string.strip("(),")
    if tuple_string == "":
        return tuple()
    res = []
    for s in tuple_string.split(", "):
        try:
            res.append(int(s))
        except ValueError:
            if strict:
                print(
                    f"String value '{s}' could not be converted to an integer, "
                    f"'{tuple_string}' not to an integer tuple."
                )
                raise
            if s[0] == s[-1] and s[0] in ('"', "'"):
                s = s[1:-1]
            try:
                res.append(int(s))
            except ValueError:
                res.append(s)
    return tuple(res)


TSV_COLUMN_CONVERTERS = {
    "act_dur": safe_fraction,
    "quarterbeats_all_endings": safe_fraction,
    "quarterbeats": safe_fraction,
    "next": str2inttuple,
}
TSV_COLUMN_DTYPES = {"mc": int, "volta": "Int64"}


def apply_function_to_directory(
    func: Callable[[Path | str], MeasureMap],
    directory: Path | str,
    output_directory: Optional[Path | str] = None,
    file_regex: str = "*",
    extensions: Optional[str | Iterable[str]] = None,
    measure_map_extension: str = ".mm.json",
):
    directory = resolve_dir(directory)
    if output_directory is not None:
        output_directory = resolve_dir(output_directory)
    if extensions is None:
        extensions = get_m21_input_extensions()
    elif isinstance(extensions, str):
        extensions = [extensions]
    paths = directory.rglob(file_regex)
    module_logger.info(
        f"Iterating through paths within {directory} that match the regex {file_regex!r} and have one "
        f"of these extensions: {extensions!r}"
    )
    for filepath in paths:
        if not any(filepath.name.endswith(ext) for ext in extensions):
            module_logger.debug(
                f"Skipping {filepath}: Extension {filepath.suffix} not in {extensions}"
            )
            continue
        try:
            mm = func(filepath)
        except Exception as e:
            module_logger.warning(
                f"Extracting MeasureMap from {filepath} failed with\n{e!r}"
            )
            continue

        input_folder = filepath.parent
        if output_directory is None:
            output_folder = input_folder
        else:
            output_folder = output_directory / input_folder.relative_to(directory)
        output_filepath = make_measure_map_filepath(
            filepath, measure_map_extension, output_folder
        )
        mm.to_json_file(output_filepath)
        module_logger.info(f"Extracted MeasureMap {output_filepath} from {filepath}.")


def collect_measure_maps(directory: Path | str) -> List[str]:
    """Returns all filepaths under the given directory that end with '.measuremap.json'."""
    directory = os.path.abspath(os.path.expanduser(directory))
    filepaths = []
    for folder, subfolders, filenames in os.walk(directory):
        subfolders[:] = [s for s in subfolders if not s.startswith(".")]
        for filename in filenames:
            if filename.endswith(".mm.json"):
                filepaths.append(os.path.join(directory, folder, filename))
    return filepaths


def get_m21_input_extensions() -> Tuple[str, ...]:
    """Returns all file extensions that music21 can parse."""
    ext2converter = converter.Converter.getSubConverterFormats()
    extensions = list(ext2converter.keys()) + [".mxl", ".krn"]
    return tuple(ext if ext[0] == "." else f".{ext}" for ext in extensions)


def make_measure_map_filepath(
    filepath: Path,
    measure_map_extension: str = ".mm.json",
    output_folder: Optional[Path] = None,
):
    output_folder.mkdir(parents=True, exist_ok=True)
    if not measure_map_extension.endswith(".json"):
        warnings.warn(
            f"measure_map_extension should end with '.json', got: {measure_map_extension!r}"
        )
    output_filename = filepath.stem + measure_map_extension
    output_filepath = output_folder / output_filename
    return output_filepath


def load_tsv(
    path, index_col=None, sep="\t", converters={}, dtype={}, stringtype=False, **kwargs
) -> Optional[pd.DataFrame]:
    """Loads the TSV file `path` while applying correct type conversion and parsing tuples.

    Copied from ms3.utils.functions

    Parameters
    ----------
    path : :obj:`str`
        Path to a TSV file as output by format_data().
    index_col : :obj:`list`, optional
        By default, the first two columns are loaded as MultiIndex.
        The first level distinguishes pieces and the second level the elements within.
    converters, dtype : :obj:`dict`, optional
        Enhances or overwrites the mapping from column names to types included the constants.
    stringtype : :obj:`bool`, optional
        If you're using pandas >= 1.0.0 you might want to set this to True in order
        to be using the new `string` datatype that includes the new null type `pd.NA`.
    """

    if converters is None:
        conv = None
    else:
        conv = dict(TSV_COLUMN_CONVERTERS)
        conv.update(converters)

    if dtype is None:
        types = None
    elif isinstance(dtype, str):
        types = dtype
    else:
        types = dict(TSV_COLUMN_DTYPES)
        types.update(dtype)

    if stringtype:
        types = {col: "string" if typ == str else typ for col, typ in types.items()}
    try:
        df = pd.read_csv(
            path, sep=sep, index_col=index_col, dtype=types, converters=conv, **kwargs
        )
    except pd.EmptyDataError:
        return
    if "mn" in df:
        mn_volta = mn2int(df.mn)
        df.mn = mn_volta.mn
        if mn_volta.volta.notna().any():
            if "volta" not in df.columns:
                df["volta"] = pd.Series(pd.NA, index=df.index).astype("Int64")
            df.volta.fillna(mn_volta.volta, inplace=True)
    return df


def mn2int(mn_series):
    """Turn a series of measure numbers parsed as strings into two integer columns 'mn' and 'volta'.

    Copied from ms3.utils.functions.
    """
    try:
        split = mn_series.fillna("").str.extract(r"(?P<mn>\d+)(?P<volta>[a-g])?")
    except Exception:
        mn_series = pd.DataFrame(mn_series, columns=["mn", "volta"])
        try:
            return mn_series.astype("Int64")
        except Exception:
            return mn_series
    split.mn = pd.to_numeric(split.mn)
    split.volta = pd.to_numeric(
        split.volta.map({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})
    )
    return split.astype("Int64")


def time_signature2nominal_length(time_signature: str) -> float:
    """Converts the given time signature into a fraction and then into the corresponding length in quarter notes."""
    assert isinstance(time_signature, str), (
        f"time_signature must be a string, got {type(time_signature)!r}: "
        f"{time_signature!r}"
    )
    try:
        ts_frac = Fraction(time_signature)
    except ValueError:
        raise ValueError(f"Invalid time signature: {time_signature!r}")
    return ts_frac * 4.0


def resolve_dir(d: Path | str) -> Path:
    """Resolves '~' to HOME directory and turns ``d`` into an absolute path."""
    if d is None:
        return None
    d = str(d)
    if os.path.isfile(d):
        raise ValueError(f"Expected a directory, got a file: {d!r}")
    if "~" in d:
        return Path(os.path.expanduser(d))
    return Path(os.path.abspath(d))


def store_json(
    data: dict | list,
    filepath: Path | str,
    indent: int = 2,
    make_dirs: bool = True,
    **kwargs,
):
    """Serialize object to file.

    Args:
        data: Nested structure of dicts and lists.
        filepath: Path to the text file to (over)write.
        indent: Prettify the JSON layout. Default indentation: 2 spaces
        make_dirs: If True (default), create the directory if it does not exist.
        **kwargs: Keyword arguments passed to :meth:`json.dumps`.
    """
    filepath = str(filepath)
    kwargs = dict(indent=indent, **kwargs)
    if make_dirs:
        directory = os.path.dirname(filepath)
        os.makedirs(directory, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, **kwargs)
