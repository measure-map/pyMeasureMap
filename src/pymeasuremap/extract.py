"""Generate MeasureMaps from scores and annotation files."""
import logging
import warnings
from pathlib import Path
from typing import Iterable, Optional

from music21 import bar, converter, stream

from pymeasuremap.base import MeasureMap
from pymeasuremap.utils import get_m21_input_extensions, resolve_dir

module_logger = logging.getLogger(__name__)


def m21_part_to_measure_map(this_part: stream.Part) -> MeasureMap:
    """
    Mapping from a music21.stream.part
    to a "measure map": currently a list of dicts with the following keys:
        "count": int,  # all represented, in natural numbers
        "qstamp": int | float,  # quarterLength from beginning
        "number" / tag: int | str,  # constraints are conventional only
        "time_signature": str | music21.meter.TimeSignature.ratioString,
        "nominal_length": int | float  # NB can derive nominal_length from TS but not vice versa
        "actual_length": int | float,  # expressed in quarterLength. Could also be as proportion
        "start_repeat": bool,
        "end_repeat": bool
        "next": lst of str
    """

    sheet_measure_map = []
    go_back_to = 1
    go_forward_from = 1
    time_sig = this_part.getElementsByClass(stream.Measure)[0].timeSignature.ratioString
    count = 1

    for measure in this_part.recurse().getElementsByClass(stream.Measure):
        end_repeat = False
        start_repeat = False
        next = []

        if measure.timeSignature:
            time_sig = measure.timeSignature.ratioString

        if measure.leftBarline:  # TODO: Replace with normal equality checks
            if str(measure.leftBarline) == str(bar.Repeat(direction="start")):
                start_repeat = True
        if measure.rightBarline:
            if str(measure.rightBarline) == str(bar.Repeat(direction="end")):
                end_repeat = True

        if (
            start_repeat
        ):  # Crude method to add next measure information including for multiple endings from repeats
            go_back_to = count
        elif measure.leftBarline:
            if (
                measure.leftBarline.type == "regular"
                and sheet_measure_map[count - 2]["end_repeat"]
            ):
                sheet_measure_map[go_forward_from - 1]["next"].append(count)
            elif measure.leftBarline.type == "regular":
                go_forward_from = count - 1
        if end_repeat:
            next.append(go_back_to)
        if count + 1 <= len(
            this_part.recurse().getElementsByClass(stream.Measure)
        ) and not (end_repeat and count > go_forward_from != 1):
            next.append(count + 1)

        measure_dict = {
            # ID
            "count": count,
            "qstamp": measure.offset,
            "number": measure.measureNumber,
            # "name"
            "time_signature": time_sig,
            "nominal_length": measure.barDuration.quarterLength,
            "actual_length": measure.duration.quarterLength,
            "start_repeat": start_repeat,
            "end_repeat": end_repeat,
            "next": next,
        }

        sheet_measure_map.append(measure_dict)
        count += 1

    return MeasureMap.from_dicts(sheet_measure_map)


def m21_stream_to_measure_map(
    this_stream: stream.Stream, check_parts_match: bool = True
) -> MeasureMap:
    """
    Maps from a music21 stream
    to a possible version of the "measure map".
    The bulk of the work is done by part_to_measure_map
    (see notes there).
    The additional check_parts_match argument defaults to False but
    if True and the score has multiple parts, it will
    check that those parts return the same measurement information.
    """

    if isinstance(this_stream, stream.Part):
        return m21_part_to_measure_map(this_stream)

    if not isinstance(this_stream, stream.Score):
        raise ValueError("Only accepts a stream.Part or stream.Score")

    measure_map = m21_part_to_measure_map(this_stream.parts[0])

    if not check_parts_match:
        return measure_map

    num_parts = len(this_stream.parts)

    if num_parts < 2:
        return measure_map

    for part in range(1, num_parts):
        part_measure_map = m21_part_to_measure_map(this_stream.parts[part])
        if part_measure_map != measure_map:
            raise ValueError(f"Parts 0 and {part} do not match.")

    return measure_map


def m21_filepath_to_measure_map(
    source_filepath: Path | str,
):
    source_filepath = Path(source_filepath)
    if not source_filepath.is_file():
        raise ValueError(f"Expected an existing file, got: {source_filepath!r}")

    if source_filepath.suffix == ".txt":
        source_stream = converter.parse(source_filepath, format="Romantext")
    else:
        source_stream = converter.parse(source_filepath)
    return m21_stream_to_measure_map(source_stream)


def extract_directory(
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
            mm = m21_filepath_to_measure_map(filepath)
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
