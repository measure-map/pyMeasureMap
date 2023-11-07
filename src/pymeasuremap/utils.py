from __future__ import annotations

import json
import os
import warnings
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from music21 import converter

from pymeasuremap.base import MeasureMap
from pymeasuremap.extract import module_logger


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
