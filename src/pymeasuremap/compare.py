"""Comparing MeasureMaps pertaining two the same music."""
import logging
from pathlib import Path
from typing import Optional

from pymeasuremap.base import MeasureMap

module_logger = logging.getLogger(__name__)


def resolve_measure_map_argument(mm: MeasureMap | Path | str | dict) -> MeasureMap:
    if isinstance(mm, MeasureMap):
        return mm
    if isinstance(mm, (Path, str)):
        return MeasureMap.from_json_file(mm)
    if isinstance(mm, dict):
        return MeasureMap.from_dicts(mm)
    raise TypeError(
        f"Expected a MeasureMap, a path to a JSON file, or a dict, got: {mm!r}"
    )


class Compare:
    def __init__(
        self,
        preferred: MeasureMap | Path | str | dict,
        other: MeasureMap | Path | str | dict,
    ):
        self.preferred_mm = resolve_measure_map_argument(preferred)
        self.other_mm = resolve_measure_map_argument(other)

    def all_identical(
        self,
        ID: bool = False,
        count: bool = True,
        qstamp: bool = True,
        number: bool = True,
        name: bool = False,
        time_signature: bool = True,
        nominal_length: bool = True,
        actual_length: bool = True,
        start_repeat: bool = True,
        end_repeat: bool = True,
        next: bool = True,
    ) -> bool:
        """Compare two measure maps and return True if the activated fields are identical, False otherwise."""
        if len(self.preferred_mm) != len(self.other_mm):
            module_logger.warning(
                f"Lengths differ: {len(self.preferred_mm)} != {len(self.other_mm)}"
            )
            return False
        mask = (
            ID,
            count,
            qstamp,
            number,
            name,
            time_signature,
            nominal_length,
            actual_length,
            start_repeat,
            end_repeat,
            next,
        )
        for preferred_tup, other_tup in zip(
            self.preferred_mm.iter_tuples(*mask), self.other_mm.iter_tuples(*mask)
        ):
            if preferred_tup != other_tup:
                verbal_mask = ", ".join(
                    field
                    for field, include in zip(
                        (
                            "ID",
                            "count",
                            "qstamp",
                            "number",
                            "name",
                            "time_signature",
                            "nominal_length",
                            "actual_length",
                            "start_repeat",
                            "end_repeat",
                            "next",
                        ),
                        mask,
                    )
                    if include
                )
                module_logger.warning(
                    f"Encountered mismatch when comparing the following entries:\n"
                    f"{verbal_mask}\n"
                    f"{preferred_tup}\n"
                    f"{other_tup}"
                )
                return False
        return True

    def quick_diagnosis(
        self,
        ID: bool = False,
        count: bool = True,
        qstamp: bool = True,
        number: bool = True,
        name: bool = False,
        time_signature: bool = True,
        nominal_length: bool = True,
        actual_length: bool = True,
        start_repeat: bool = True,
        end_repeat: bool = True,
        next: bool = True,
        entries_threshold: Optional[int] = None,
    ) -> str:
        """Compare two measure maps and return a quick analysis. 'OK' = perfect match."""
        if len(self.preferred_mm) != len(self.other_mm):
            if entries_threshold is None:
                return "entries"
            n_diff = abs(len(self.preferred_mm) - len(self.other_mm))
            if n_diff > entries_threshold:
                return f">{entries_threshold}_entries"
            else:
                return f"≤{entries_threshold}_entries"
        mask = (
            ID,
            count,
            qstamp,
            number,
            name,
            time_signature,
            nominal_length,
            actual_length,
            start_repeat,
            end_repeat,
            next,
        )
        for preferred_tup, other_tup in zip(
            self.preferred_mm.iter_tuples(*mask), self.other_mm.iter_tuples(*mask)
        ):
            if preferred_tup != other_tup:
                verbal_mask = (
                    field
                    for field, include in zip(
                        (
                            "ID",
                            "count",
                            "qstamp",
                            "number",
                            "name",
                            "time_signature",
                            "nominal_length",
                            "actual_length",
                            "start_repeat",
                            "end_repeat",
                            "next",
                        ),
                        mask,
                    )
                    if include
                )
                for field, preferred_value, other_value in zip(
                    verbal_mask, preferred_tup, other_tup
                ):
                    if preferred_value != other_value:
                        return field
        return "OK"

    def diagnose(self) -> list[tuple]:
        """Returns the changes that would align the other MeasureMap with the preferred one, without modifying
        either of them."""
        if len(self.preferred_mm) != len(self.other_mm):
            diagnosis = self.compare_lengths()
            if not diagnosis:
                diagnosis.append(
                    ("Needleman-Wunsch",)
                    + needleman_wunsch_algorithm(
                        self.preferred_mm.entries, self.other_mm.entries
                    )
                )
            return diagnosis
        diagnosis = []
        for preferred, other in zip(self.preferred_mm, self.other_mm):
            if preferred.start_repeat != other.start_repeat:
                diagnosis.append(("Repeat_Marks", preferred.count, "start"))
            if preferred.end_repeat != other.end_repeat:
                diagnosis.append(("Repeat_Marks", preferred.count, "end"))
            if preferred.actual_length != other.actual_length:
                diagnosis.append(
                    ("Measure_Length", preferred.count, preferred.actual_length)
                )
            if preferred.time_signature != other.time_signature:
                diagnosis.append(
                    ("Time_Signature", preferred.count, preferred.time_signature)
                )
        if any(
            preferred.number != other.number
            for preferred, other in zip(self.preferred_mm, self.other_mm)
        ):
            diagnosis.append(("Renumber", "all"))
        return diagnosis

    def compare_lengths(self) -> list[tuple]:
        """Returns the joins and splits of measures in the other MeasureMap that would make the actual lengths
        match the preferred one."""
        diagnosis = []
        preferred, other = self.preferred_mm.entries, self.other_mm.entries
        for i in range(min(len(preferred), len(other)) - 1):
            if (
                preferred[i].actual_length
                == other[i].actual_length + other[i + 1].actual_length
            ):
                diagnosis.append(("Join", i + 1))
            if (
                preferred[i].actual_length + preferred[i + 1].actual_length
                == other[i].actual_length
            ):
                diagnosis.append(("Split", i + 1, preferred[i].actual_length))
        return diagnosis


# region helpers


def needleman_wunsch_algorithm(preferred_mm, other_mm):
    """
    A standard alignment algorithm of some (limited) use for this use case.
    # TODO: make output easier to interpret for end user?
    """

    n = len(preferred_mm)
    m = len(other_mm)
    match_score = 1
    mismatch_score = -1
    gap_penalty = -1
    # continue_gap_penalty = -1  # TODO: needleman_wunsch to prioritise continuing gaps over new gaps

    preferred_comparer = []
    other_comparer = []
    keys = ["actual_length", "time_signature", "start_repeat", "end_repeat"]

    for x in preferred_mm:
        preferred_comparer.append({y: getattr(x, y) for y in keys})
    for x in other_mm:
        other_comparer.append({y: getattr(x, y) for y in keys})  # TODO: remove?

    matrix = [[0 for _ in range(m + 1)] for _ in range(n + 1)]

    for i in range(1, n + 1):
        matrix[i][0] = matrix[i - 1][0] + gap_penalty
    for j in range(1, m + 1):
        matrix[0][j] = matrix[0][j - 1] + gap_penalty

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            match = matrix[i - 1][j - 1] + (
                match_score
                if preferred_comparer[i - 1] == other_comparer[j - 1]
                else mismatch_score
            )
            delete = matrix[i - 1][j] + gap_penalty
            insert = matrix[i][j - 1] + gap_penalty
            matrix[i][j] = max(match, delete, insert)

    preferred_aligned, other_aligned = [], []
    i, j = n, m
    while i > 0 and j > 0:
        score = matrix[i][j]
        diag = matrix[i - 1][j - 1]
        up = matrix[i][j - 1]
        left = matrix[i - 1][j]
        if score == left + gap_penalty:
            preferred_aligned.append(preferred_mm[i - 1])
            other_aligned.append(None)
            i -= 1
        elif score == up + gap_penalty:
            preferred_aligned.append(None)
            other_aligned.append(other_mm[j - 1])
            j -= 1
        elif score == diag + (
            match_score
            if preferred_comparer[i - 1] == other_comparer[j - 1]
            else mismatch_score
        ):
            preferred_aligned.append(preferred_mm[i - 1])
            other_aligned.append(other_mm[j - 1])
            i -= 1
            j -= 1
    while i > 0:
        preferred_aligned.append(preferred_mm[i - 1])
        other_aligned.append(None)
        i -= 1
    while j > 0:
        preferred_aligned.append(None)
        other_aligned.append(other_mm[j - 1])
        j -= 1

    return preferred_aligned[::-1], other_aligned[::-1]


# endregion helpers
# region operations


def write_diagnosis(
    diagnosis: list[list], out_path: Path, out_name: str = "other_modifications.txt"
) -> None:
    """Write the diagnosis (suggested modifications to the `other` source) in a text file"""
    with open(out_path / out_name, "w") as file:
        if not diagnosis:
            file.write("No changes required to align these two sources.")
            return

        file.write("Changes to be made to secondary measure map:\n")
        for change in diagnosis:
            if change[0] == "Join":
                file.write(f" - Join measures {change[1]} and {change[1] + 1}.\n")
            elif change[0] == "Split":
                file.write(f" - Split measure {change[1]} at offset {change[2]}.\n")
            elif change[0] == "Expand_Repeats":
                file.write(" - Expand the repeats.\n")
            elif change[0] == "Renumber":
                file.write(" - Renumber the measures.\n")
            elif change[0] == "Repeat_Marks":
                file.write(f" - Add {change[2]} repeat marks to measure {change[1]}.\n")
            elif change[0] == "Measure_Length":
                file.write(
                    f" - Change measure {change[1]} actual length to {change[2]}.\n"
                )
            elif change[0] == "Time_Signature":
                file.write(
                    f" - Change measure {change[1]} time signature to {change[2]}.\n"
                )


def one_comparison(preferred_path: Path, other_path: Path, write: bool = True) -> list:
    diagnosis = Compare(preferred_path, other_path).diagnose()

    if write:
        write_diagnosis(diagnosis, preferred_path.parent, "other_modifications.txt")

    return diagnosis


def run_corpus(
    base_path: Path,  # "When-in-Rome" / "Corpus" / "Chorale-Corpus",
    preferred_name: str = "preferred_measure_map.json",
    other_name: str = "other_measure_map.json",
) -> None:
    """
    Run comparisons on a corpus of pre-extracted measure maps.
    Set up with defaults for a local copy of `When in Rome` where the directory structure has
    pairs of corresponding `preferred` and `other`
    sources in the same folder.
    """
    for pref_path in base_path.rglob(preferred_name):
        other_path = pref_path.parent / other_name
        one_comparison(pref_path, other_path)


# endregion operations
