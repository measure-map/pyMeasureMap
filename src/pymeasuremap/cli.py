"""
Commandline Interface for pyMeasureMap.
All commands accessible by typing ``MM`` after pip-installing this package.
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import List, Tuple

from pymeasuremap import __version__

__license__ = "CC BY-SA 4.0"

from pymeasuremap.compare import compare_pairs, one_comparison, run_corpus
from pymeasuremap.convert import convert_directory
from pymeasuremap.extract import extract_directory
from pymeasuremap.utils import get_m21_input_extensions, resolve_dir

module_logger = logging.getLogger(__name__)


# ---- Python API ----
# The functions defined in this section can be imported by users in their
# Python scripts/interactive interpreter, e.g. via
# `from pymeasuremap.skeleton import fib`,
# when using this Python module as a library.


def compare_cmd(args):
    print("Comparing MeasureMaps...")
    if args.pairs is not None or args.other is not None:
        try:
            layered_compare_cmd(args)
        except ValueError as e:
            sys.exit(f"MM compare: error: {e}")
        except OSError as e:
            path = args.pairs if e.filename is None else e.filename
            sys.exit(f"MM compare: error: {path}: {e.strerror}")
        return
    if args.files is None:
        run_corpus(args.dir)
    else:
        for pref_path in args.files:
            other_path = pref_path.parent / "other_measure_map.json"
            one_comparison(pref_path, other_path)


def read_pairs_file(
    filepath: Path | str, directory: Path | str
) -> List[Tuple[Path, Path]]:
    """Reads a TSV or CSV file whose first two columns contain the paths of the preferred and the other MeasureMap.

    * The columns are separated by tabs if the first line contains one, otherwise by commas. Cells may be quoted.
    * Relative paths are resolved against the directory (not against the location of the pairs file).
    * The first row is skipped as a header if its first cell is neither an existing file nor ends on '.json'.
    * Rows with fewer than two filled cells are skipped.

    Raises:
        ValueError: If the file does not contain any pair.
    """
    with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
        f.seek(0)
        delimiter = "\t" if "\t" in first_line else ","
        rows = [
            [cell.strip() for cell in row] for row in csv.reader(f, delimiter=delimiter)
        ]
    pairs = []
    for i, row in enumerate(rows):
        if len(row) < 2 or not row[0] or not row[1]:
            continue
        preferred, other = resolve_files_argument(row[:2], directory)
        is_header = (
            i == 0 and not preferred.is_file() and not row[0].lower().endswith(".json")
        )
        if not is_header:
            pairs.append((preferred, other))
    if not pairs:
        raise ValueError(
            f"{filepath} does not contain any pair of MeasureMap paths. Expected two columns separated by tabs "
            f"or commas."
        )
    return pairs


def layered_compare_cmd(args):
    """Runs the layered comparison on the pairs given via --pairs or via -f and --other.

    Wrong combinations of these arguments end the program like any other usage error (usage message, exit
    status 2).

    Raises:
        ValueError: If the pairs file does not contain any pair.
    """
    if args.pairs is not None:
        if args.files or args.other:
            args.parser.error("Pass either --pairs or -f together with --other.")
        pairs = read_pairs_file(args.pairs, args.dir)
    else:
        if not args.files:
            args.parser.error(
                "Pass the preferred MeasureMap(s) via -f when using --other."
            )
        others = resolve_files_argument(args.other, args.dir)
        if len(others) == 1:
            others = others * len(args.files)
        if len(others) != len(args.files):
            args.parser.error("Pass either one or as many --other files as -f files.")
        pairs = list(zip(args.files, others))
    summary, reports = compare_pairs(pairs, output_directory=args.out)
    for report in reports:
        if report is not None:
            print(report.to_text())
    for row in summary[summary.verdict == "error"].itertuples():
        print(f"{row.preferred} vs. {row.other}: ERROR {row.message}")
    if args.out is not None:
        print(
            f"Wrote the summary of {len(summary)} comparison(s) to {Path(args.out) / 'comparison_summary.tsv'}"
        )


def convert_cmd(args):
    convert_directory(
        directory=args.dir,
        output_directory=args.out,
        file_regex=args.regex,
        extensions=args.extensions,
        measure_map_extension=args.mm_extension,
    )


def extract_cmd(args):
    extract_directory(
        directory=args.dir,
        output_directory=args.out,
        file_regex=args.regex,
        extensions=args.extensions,
        measure_map_extension=args.mm_extension,
    )


def check_and_create(d) -> Path:
    """Turn input into an existing path. A directory that doesn't exist is created: after asking the user if
    standard input is a terminal, without asking otherwise (e.g., when called from a script or without standard
    input).

    Raises:
        argparse.ArgumentTypeError:
            If the path is a file, if the directory cannot be created, or if the user declines to create it.
    """
    if not os.path.isdir(d):
        if os.path.isfile(d):
            raise argparse.ArgumentTypeError(f"{d} is a file, not a directory.")
        d = resolve_dir(os.path.join(os.getcwd(), d))
        if not d.is_dir():
            ask = sys.stdin is not None and sys.stdin.isatty()
            if ask and input(f"{d} does not exist. Create? (y|n)") != "y":
                raise argparse.ArgumentTypeError(
                    f"{d} needs to be an existing directory."
                )
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise argparse.ArgumentTypeError(f"{d} cannot be created: {e.strerror}")
            if not ask:
                module_logger.info(f"Created the output directory {d}")
    return resolve_dir(d)


def check_dir(d):
    if not os.path.isdir(d):
        d = resolve_dir(os.path.join(os.getcwd(), d))
        if not os.path.isdir(d):
            raise argparse.ArgumentTypeError(f"{d} needs to be an existing directory")
    return resolve_dir(d)


def get_arg_parser():
    # reusable argument sets
    default_args = argparse.ArgumentParser(add_help=False)
    default_args.add_argument(
        "-d",
        "--dir",
        metavar="DIR",
        default=os.getcwd(),
        type=check_dir,
        help="Folder(s) that will be scanned for input files. Defaults to current working directory if no individual "
        "files are passed via -f.",
    )
    default_args.add_argument(
        "-o",
        "--out",
        metavar="OUT_DIR",
        type=check_and_create,
        help="Output directory.",
    )
    default_args.add_argument(
        "-f",
        "--files",
        metavar="PATH",
        nargs="+",
        help="List of files to process. If -d is passed, relative file paths are resolved against the given directory.",
    )
    default_args.add_argument(
        "-r",
        "--regex",
        metavar="REGEX",
        default="*",
        help="Regular expression for filtering file names. Defaults to all files.",
    )
    default_args.add_argument(
        "-l",
        "--level",
        metavar="{c, e, w, i, d}",
        default="i",
        help="Choose how many log messages you want to see: c (none), e, w, i, d (maximum)",
    )

    # main argument parser
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
-----------------------------
| Welcome to pyMeasureMaps! |
-----------------------------

The library offers you the following commands. Add the flag -h to one of them to learn about its parameters.
""",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(
        help="The action that you want to perform.", dest="action"
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare MeasureMaps pertaining to the same music.",
        description="""Compare MeasureMaps pertaining to the same music. There are two modes:

Layered comparison (with --other or --pairs): Compares a preferred MeasureMap with another one and reports whether
they are identical, differ in numbering or repeats only, are the same when unfolded, can be aligned by joining and
splitting measures, or are different, together with the measures concerned. In this mode, -f names the preferred
MeasureMap(s). Prints one report per pair; with -o, also writes comparison_summary.tsv plus a measure table (.tsv)
and the report (.txt) for each pair that is not identical.

    MM compare -f preferred.mm.json --other other.mm.json
    MM compare -d corpus --pairs pairs.tsv -o reports

Diagnosis (without --other and --pairs): For each preferred MeasureMap, i.e. each file passed via -f or each file
called preferred_measure_map.json under -d, looks for other_measure_map.json in the same folder and writes the
suggested modifications to other_modifications.txt next to it. -o is ignored in this mode.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[default_args],
    )
    compare_parser.add_argument(
        "--other",
        metavar="PATH",
        nargs="+",
        help="Perform a layered comparison of the MeasureMap(s) passed via -f (preferred) with the one(s) passed "
        "here. Pass either one file or as many as via -f. Relative paths are resolved against -d.",
    )
    compare_parser.add_argument(
        "--pairs",
        metavar="TSV",
        help="Perform a layered comparison for each row of the given TSV/CSV file whose first two columns contain "
        "the paths of a preferred and an other MeasureMap (separated by tabs or commas, with or without a header "
        "row). Relative paths are resolved against -d. Cannot be combined with -f and --other.",
    )
    compare_parser.set_defaults(func=compare_cmd, parser=compare_parser)

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert non-score formats to measure maps. Currently, conversion is implemented for .tsv 'measures' "
        "tables output by the ms3 parser.",
        parents=[default_args],
    )
    convert_parser.add_argument(
        "-x",
        "--extensions",
        nargs="+",
        default=[".tsv"],
        help="File extensions to discover and convert to MeasureMaps. Defaults to '.tsv'.",
    )
    convert_parser.add_argument(
        "--mm-extension",
        default=".mm.json",
    )
    convert_parser.set_defaults(func=convert_cmd)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Generate MeasureMaps from scores and annotation files.",
        parents=[default_args],
    )
    extract_parser.add_argument(
        "-x",
        "--extensions",
        nargs="+",
        default=get_m21_input_extensions(),
        help="File extensions for which to extract MeasureMaps. Defaults to all extensions supported by music21.",
    )
    extract_parser.add_argument(
        "--mm-extension",
        default=".mm.json",
    )
    extract_parser.set_defaults(func=extract_cmd)

    return parser


def resolve_files_argument(files: List[str], directory: str) -> List[Path]:
    """Resolves relative file paths against the given directory."""
    filepaths = [
        filepath if os.path.isabs(filepath) else os.path.join(directory, filepath)
        for filepath in files
    ]
    return [Path(filepath) for filepath in filepaths]


def resolve_level_param(level):
    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "NOTSET": logging.NOTSET,
        "D": logging.DEBUG,
        "I": logging.INFO,
        "W": logging.WARNING,
        "E": logging.ERROR,
        "C": logging.CRITICAL,
        "N": logging.NOTSET,
    }
    if isinstance(level, str):
        level = LEVELS[level.upper()]
    assert isinstance(
        level, int
    ), f"Logging level needs to be an integer, not {level.__class__}"
    return level


def setup_logging(loglevel: str | int = logging.INFO):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    loglevel = resolve_level_param(loglevel)
    logformat = "%(levelname)-8s %(name)s -- %(pathname)s (line %(lineno)s) in %(funcName)s():\n\t%(message)s"
    logging.basicConfig(
        level=loglevel, stream=sys.stdout, format=logformat, datefmt="%Y-%m-%d %H:%M:%S"
    )


def run():
    """Parse arguments and pass them to the function corresponding to the respective MM command."""
    parser = get_arg_parser()
    args = parser.parse_args()
    if "func" not in args:
        parser.print_help()
        return
    setup_logging(args.level)
    if args.files is not None:
        args.files = resolve_files_argument(args.files, args.dir)
    args.dir = resolve_dir(args.dir)
    module_logger.debug(f"Calling {args.func.__name__} with args={args}")
    args.func(args)


if __name__ == "__main__":
    run()
