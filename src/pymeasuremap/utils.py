from __future__ import annotations

import json
import os
from fractions import Fraction
from pathlib import Path
from typing import List, Tuple

from music21 import converter


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
    extensions = list(ext2converter.keys()) + [".mxl"]
    return tuple(ext if ext[0] == "." else f".{ext}" for ext in extensions)


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
