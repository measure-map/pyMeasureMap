"""Generate MeasureMaps from any score that Verovio can read (MEI, MusicXML, Humdrum, ABC, PAE, ...).

Requires the optional dependency ``verovio`` (``pip install pyMeasureMap[verovio]``).

How the fields are obtained:

- ``ID``: ``measure/@xml:id`` of the MEI document (kept from MEI input; generated deterministically for other input).
- ``count``, ``number``, ``name``, ``time_signature``, ``start_repeat``, ``end_repeat``: read from the notated MEI
  (see :mod:`pymeasuremap.mei`).
- ``qstamp`` and ``actual_length``: Verovio's timemap of the notated (unexpanded) score, which reflects the actual
  content of each measure (the longest staff).
- ``next``: inferred from repeat barlines, voltas, and jump markers (see :mod:`pymeasuremap.repeats`). If the score
  contains an ``<expansion>`` (MEI) or is MusicXML (for which Verovio builds one on import), the inferred successors
  can be checked against Verovio's unfolding, or taken from it with ``next_from="expansion"``.
"""

from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional, Tuple

from pymeasuremap.base import Measure, MeasureMap
from pymeasuremap.mei import MeiMeasure, parse_mei_measures
from pymeasuremap.repeats import END, infer_next, successors
from pymeasuremap.utils import apply_function_to_directory

module_logger = logging.getLogger(__name__)

MEI_NAMESPACE = "http://www.music-encoding.org/ns/mei"

VEROVIO_INPUT_EXTENSIONS = (
    ".mei",
    ".musicxml",
    ".mxl",
    ".xml",
    ".krn",
    ".abc",
    ".pae",
)

NextFrom = Literal["inference", "expansion"]
NextAs = Literal["count", "ID"]


def _import_verovio():
    try:
        import verovio
    except ImportError as e:
        raise ImportError(
            "Extracting MeasureMaps with Verovio requires the optional dependency 'verovio'. Install it via "
            "`pip install pyMeasureMap[verovio]`."
        ) from e
    return verovio


def load_toolkit(source: Path | str, options: Optional[dict] = None, **kwargs):
    """Loads a file path or a string containing a score into a fresh Verovio toolkit.

    Args:
        source: A path to a file or the content of a score as a string.
        options: Verovio options. Default: ``{"xmlIdChecksum": True}`` to produce stable IDs for formats without IDs.
        **kwargs: Further options that update ``options``.
    """
    verovio = _import_verovio()
    tk = verovio.toolkit()
    tk.setOptions({"xmlIdChecksum": True, **(options or {}), **kwargs})
    if isinstance(source, Path) or (
        isinstance(source, str) and "\n" not in source and os.path.isfile(source)
    ):
        loaded = tk.loadFile(str(source))
    else:
        loaded = tk.loadData(source)
    if not loaded:
        raise ValueError(f"Verovio could not load the score:\n{tk.getLog()}")
    return tk


def measure_onsets(tk) -> Tuple[List[Tuple[str, Fraction]], Fraction]:
    """Returns the ``(measure ID, qstamp)`` pairs in the order of Verovio's timemap and the end of the last event."""
    timemap = tk.renderToTimemap(
        {"includeMeasures": True, "includeRests": True, "useFractions": True}
    )
    onsets = [
        (e["measureOn"], Fraction(*e["qfrac"])) for e in timemap if "measureOn" in e
    ]
    end = Fraction(*timemap[-1]["qfrac"]) if timemap else Fraction(0)
    return onsets, end


def expansion_next(mei: str, measure_ids: List[str]) -> List[list]:
    """Successors (0-based indices) according to Verovio's unfolding of the score's ``<expansion>``.

    Measures that Verovio does not play get no successors; the last measure played is followed by :data:`END`.
    """
    tk = load_toolkit(mei)
    performed, _ = measure_onsets(tk)
    index = {measure_id: i for i, measure_id in enumerate(measure_ids)}
    sequence = [
        index[notated]
        for notated in (tk.getNotatedIdForElement(mid) for mid, _ in performed)
        if notated in index
    ]
    return successors(sequence + [END], len(measure_ids))


def compare_next(
    inferred: List[list], other: List[list]
) -> List[Tuple[int, list, list]]:
    """Returns ``(index, inferred, other)`` for all measures whose successors differ, ignoring :data:`END`."""
    differences = []
    for i, (a, b) in enumerate(zip(inferred, other)):
        a_set = {x for x in a if x is not END}
        b_set = {x for x in b if x is not END}
        if a_set != b_set:
            differences.append((i, sorted(a_set), sorted(b_set)))
    return differences


def _original_mei(source: Path | str) -> Optional[str]:
    """Returns the source itself if it is MEI. Parsing the original keeps its exact structure (Verovio's re-encoding
    may differ, e.g. drop misplaced measures)."""
    if isinstance(source, Path) or (
        isinstance(source, str) and "\n" not in source and os.path.isfile(source)
    ):
        if Path(source).suffix.lower() != ".mei":
            return None
        with open(source, encoding="utf-8") as f:
            return f.read()
    if MEI_NAMESPACE in source[:2000]:
        return source
    return None


def _number_and_name(measures: List[MeiMeasure]) -> Tuple[List[int], List[str]]:
    """Measure numbers follow ``@n``; measures without a number (e.g. the second part of a split measure) carry the
    number of their predecessor. Names add a letter for the volta, as in '16a', '16b'.
    """
    numbers, names = [], []
    previous = 0
    for m in measures:
        digits = re.match(r"\s*(\d+)", m.n or "")
        number = int(digits.group(1)) if digits else previous
        previous = number
        numbers.append(number)
        name = str(number)
        if m.ending_numbers:
            name += chr(96 + m.ending_numbers[0])  # 1 -> 'a', 2 -> 'b', ...
        names.append(name)
    return numbers, names


def _format_next(
    next_indices: List[list], measures: List[MeiMeasure], next_as: NextAs
) -> List[list]:
    formatted = []
    for successors_ in next_indices:
        if next_as == "count":
            formatted.append([-1 if x is END else x + 1 for x in successors_])
        else:
            formatted.append([measures[x].ID for x in successors_ if x is not END])
    return formatted


def verovio_to_measure_map(
    source: Path | str,
    next_from: NextFrom = "inference",
    next_as: NextAs = "count",
    check_expansion: bool = True,
    options: Optional[dict] = None,
) -> MeasureMap:
    """Creates a MeasureMap from a score, using Verovio for parsing.

    Args:
        source: Path to a score file or a string with the score's content.
        next_from:
            'inference' (default) derives 'next' from the notated repeat structure.
            'expansion' uses Verovio's unfolding of the score's (first) ``<expansion>`` and falls back to inference
            if there is none.
        next_as:
            'count' (default) fills 'next' with the 'count' values of the successors and -1 for the end of the piece
            (the convention of ms3 measures tables). 'ID' uses the successors' IDs and leaves out the end.
        check_expansion: If the score has an ``<expansion>``, log the measures where it disagrees with the inference.
        options: Verovio options to be used when loading the score.

    Returns:
        A MeasureMap with one entry per ``<measure>``, including its ID.
    """
    tk = load_toolkit(source, options, expandNever=True)
    mei = _original_mei(source) or tk.getMEI()
    try:
        measures = parse_mei_measures(mei)
    except ET.ParseError as e:
        module_logger.warning(
            f"Could not parse the MEI ({e}), using Verovio's re-encoding instead."
        )
        mei = tk.getMEI()
        measures = parse_mei_measures(mei)
    if len(measures) < 2:
        raise ValueError(f"Need at least two measures, found {len(measures)}.")
    measure_ids = [m.ID for m in measures]

    # qstamps and actual lengths
    onsets, end = measure_onsets(tk)
    qstamp: Dict[str, Fraction] = {}
    for measure_id, onset in onsets:
        qstamp.setdefault(measure_id, onset)
    missing = [mid for mid in measure_ids if mid not in qstamp]
    if missing:
        module_logger.warning(
            f"Verovio's timemap has no onset for {len(missing)} measures, e.g. {missing[:3]}."
        )
    ordered = [qstamp.get(mid) for mid in measure_ids] + [end]
    actual_lengths = []
    for i, onset in enumerate(ordered[:-1]):
        following = next((q for q in ordered[i + 1 :] if q is not None), None)
        if onset is None or following is None:
            actual_lengths.append(None)
        else:
            actual_lengths.append(float(following - onset))

    # successors
    next_indices = infer_next(measures)
    if measures[0].has_expansion and (check_expansion or next_from == "expansion"):
        unfolded = expansion_next(mei, measure_ids)
        differences = compare_next(next_indices, unfolded)
        if differences:
            module_logger.warning(
                f"The <expansion> disagrees with the inferred repeat structure for {len(differences)} measures "
                f"(count, inferred, expansion): "
                + ", ".join(
                    f"({i + 1}, {[x + 1 for x in a]}, {[x + 1 for x in b]})"
                    for i, a, b in differences[:10]
                )
            )
        if next_from == "expansion":
            next_indices = unfolded
    elif next_from == "expansion":
        module_logger.info("The score has no <expansion>; inferring 'next' instead.")

    numbers, names = _number_and_name(measures)
    next_values = _format_next(next_indices, measures, next_as)
    entries = []
    for i, m in enumerate(measures):
        nominal_length = (
            float(Fraction(m.time_signature) * 4) if m.time_signature else None
        )
        onset = ordered[i]
        entries.append(
            Measure(
                ID=m.ID,
                count=i + 1,
                qstamp=None if onset is None else float(onset),
                number=numbers[i],
                name=names[i],
                time_signature=m.time_signature,
                nominal_length=nominal_length,
                actual_length=actual_lengths[i],
                start_repeat=m.start_repeat,
                end_repeat=m.end_repeat,
                next=next_values[i],
            )
        )
    return MeasureMap(entries)


def verovio_filepath_to_measure_map(
    source_filepath: Path | str, **kwargs
) -> MeasureMap:
    source_filepath = Path(source_filepath)
    if not source_filepath.is_file():
        raise ValueError(f"Expected an existing file, got: {source_filepath!r}")
    return verovio_to_measure_map(source_filepath, **kwargs)


def extract_directory_with_verovio(
    directory: Path | str,
    output_directory: Optional[Path | str] = None,
    file_regex: str = "*",
    extensions: Optional[str | Iterable[str]] = VEROVIO_INPUT_EXTENSIONS,
    measure_map_extension: str = ".mm.json",
):
    return apply_function_to_directory(
        func=verovio_filepath_to_measure_map,
        directory=directory,
        output_directory=output_directory,
        file_regex=file_regex,
        extensions=extensions,
        measure_map_extension=measure_map_extension,
    )
