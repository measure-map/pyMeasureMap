"""Comparing MeasureMaps pertaining to the same music."""

import logging
import os
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Tuple

from pymeasuremap.base import MeasureMap

if TYPE_CHECKING:
    import pandas as pd

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
        volta: bool = True,
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
            volta,
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
                            "volta",
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
        volta: bool = True,
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
            volta,
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
                            "volta",
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


# region layered comparison (see compare_layered() for an overview)

LAYERED_FIELDS = (
    "qstamp",
    "number",
    "name",
    "time_signature",
    "nominal_length",
    "actual_length",
    "start_repeat",
    "end_repeat",
    "volta",
    "next",
)
"""Fields compared measure by measure in layer 2 ('ID' and 'count' are excluded because they identify measures)."""

STRUCTURAL_FIELDS = ("actual_length", "time_signature")
"""Fields that need to be identical for two measures to be considered the 'same measure'."""

REPEAT_FIELDS = ("start_repeat", "end_repeat", "volta", "next")

VERDICTS = (
    "identical",
    "same_count",
    "same_measures",
    "same_count_different_measures",
    "same_when_unfolded",
    "alignable",
    "different",
)
"""Possible verdicts, from the most to the least similar:

* identical: same number of measures, all fields defined on both sides are identical.
* same_count: same number of measures, but no field is defined on both sides, so nothing else could be compared.
* same_measures: same number of measures with the same lengths and time signatures; other fields (e.g., numbering
  or repeat signs) differ.
* same_count_different_measures: same number of measures, but some lengths or time signatures differ.
* same_when_unfolded: the numbers of measures differ, but the unfolded sequences of measures are identical.
* alignable: the sequences can be aligned with joins and splits only, i.e., the music has the same total duration
  but measures are segmented differently.
* different: the alignment requires insertions, deletions, or changes of measure lengths or time signatures.

A verdict is based on the fields that both sides define. ComparisonReport.summary() lists them ('compared_fields')
and says whether measure lengths were among them ('lengths_compared'): two MeasureMaps that merely enumerate their
measures are 'identical' if they have the same number of measures with the same numbers.
"""

OPERATIONS = (
    "match",
    "change_length",
    "change_time_signature",
    "join",
    "split",
    "insert",
    "delete",
)
"""Operations of an alignment, from the point of view of the 'other' MeasureMap:

* match: the measure corresponds to one measure of the preferred MeasureMap.
* change_length: it corresponds to one preferred measure that has a different length.
* change_time_signature: it corresponds to one preferred measure of the same length that has a different time
  signature.
* join: two consecutive other measures add up to one preferred measure.
* split: one other measure corresponds to two consecutive preferred measures.
* insert: a preferred measure has no counterpart and would need to be inserted.
* delete: an other measure has no counterpart and would need to be deleted.
"""

_EPSILON = 1e-6


def _lengths_equal(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) < _EPSILON


def _values_equal(a, b) -> bool:
    if (
        isinstance(a, (int, float))
        and isinstance(b, (int, float))
        and not isinstance(a, bool)
    ):
        return _lengths_equal(a, b)
    return a == b


def _actual_length(measure) -> Optional[float]:
    try:
        return measure.get_actual_length()
    except Exception:
        return None


def _prepare(mm: MeasureMap) -> MeasureMap:
    """Decompresses the MeasureMap if it has gaps in its counts."""
    counts = [m.count for m in mm]
    if None in counts:
        return mm
    if counts != list(range(counts[0], counts[0] + len(counts))):
        return mm.decompress()
    return mm


def unfold(measure_map: MeasureMap, max_factor: int = 10) -> List[int]:
    """Returns the sequence of counts that corresponds to a play-through of the MeasureMap.

    The 'next' field is used if it is specified: When a measure is visited for the k-th time, the k-th element of its
    'next' list is the successor (the last element if the list has fewer elements). Elements can be counts or IDs;
    -1, None, or an empty list mark the end. Measures without 'next' continue with the following count.

    If no measure specifies 'next', the play-through is inferred from 'start_repeat', 'end_repeat', and 'volta':
    every repeated section is played twice, and measures belonging to a volta are played only in the pass whose
    number corresponds to the volta number. An end repeat without a start repeat goes back to the previous end
    repeat or to the beginning.

    Limitations:

    * As soon as one measure specifies 'next', the repeat signs and voltas are not interpreted anymore: measures
      without 'next' simply continue with the following count.
    * Integers in 'next' are looked up as counts first and as IDs second.
    * Repeats within repeats are not supported by the inference from repeat signs, and neither are jumps such as
      da capo or dal segno, which a MeasureMap can express through 'next' only.
    * The play-through is cut off after max_factor times the number of measures, with a warning.
    """
    measures = list(_prepare(measure_map))
    if not measures:
        return []
    by_count = {m.count: i for i, m in enumerate(measures) if m.count is not None}
    by_id = {m.ID: i for i, m in enumerate(measures) if m.ID is not None}
    max_length = max_factor * len(measures)
    if any(m.next for m in measures):

        def resolve(target) -> Optional[int]:
            if target is None or target == -1:
                return None
            if isinstance(target, int) and target in by_count:
                return by_count[target]
            if str(target) in by_id:
                return by_id[str(target)]
            module_logger.warning(
                f"Unfolding ends early because 'next' refers to {target!r}, which is neither a count nor an ID "
                f"of this MeasureMap."
            )
            return None

        sequence, visits, i = [], {}, 0
        while i is not None and len(sequence) < max_length:
            sequence.append(measures[i].count)
            k = visits.get(i, 0)
            visits[i] = k + 1
            successors = measures[i].next
            if successors is None:
                i = i + 1 if i + 1 < len(measures) else None
            elif len(successors) == 0:
                i = None
            else:
                i = resolve(successors[min(k, len(successors) - 1)])
        if i is not None:
            module_logger.warning(
                "Unfolding stopped because the 'next' fields seem to describe an endless loop."
            )
        return sequence
    # infer from repeat signs and voltas
    sequence, i = [], 0
    section_start, current_pass = 0, 1  # of the repeated section that is being played
    repeated_ends, in_voltas, skipped_volta = set(), False, False
    while i < len(measures) and len(sequence) < max_length:
        measure = measures[i]
        if measure.volta is None and in_voltas:
            # the endings are over: what follows is played once more from the first pass
            if current_pass == 1 and skipped_volta:
                module_logger.warning(
                    f"The endings before count {measure.count} do not include an end repeat: only the first one "
                    f"is part of the play-through."
                )
            section_start, current_pass = i, 1
            in_voltas, skipped_volta = False, False
        if measure.start_repeat and i != section_start and current_pass == 1:
            section_start = i
        if measure.volta is not None:
            in_voltas = True
            if measure.volta != current_pass:
                skipped_volta = True
                i += 1
                continue
        sequence.append(measure.count)
        if measure.end_repeat:
            if measure.volta is not None:
                # each ending is played in one pass only, so its end repeat is taken whenever it is reached
                i, current_pass = section_start, current_pass + 1
                in_voltas = False
                continue
            if i not in repeated_ends:
                repeated_ends.add(i)
                i, current_pass = section_start, 2
                continue
            section_start, current_pass = i + 1, 1
        i += 1
    if len(sequence) >= max_length:
        module_logger.warning(
            "Unfolding stopped because the repeat signs seem to describe an endless loop."
        )
    return sequence


def _same_measure(p: tuple, o: tuple) -> bool:
    """Whether two (count, actual_length, time_signature, ...) items describe the same measure. Lengths and time
    signatures are compared only where both sides define them: a measure without a length (e.g., from a source
    that only enumerates measures) is not different from one that has a length.
    """
    if p[1] is not None and o[1] is not None and not _lengths_equal(p[1], o[1]):
        return False
    return p[2] is None or o[2] is None or p[2] == o[2]


def _change_operation(p: tuple, o: tuple) -> str:
    """Names the operation for two paired items that are not the same measure."""
    if p[1] is not None and o[1] is not None and not _lengths_equal(p[1], o[1]):
        return "change_length"
    return "change_time_signature"


def _numbers_differ(p: tuple, o: tuple) -> bool:
    """Whether both items carry a measure number (fourth element) and the two numbers are different."""
    if len(p) < 4 or len(o) < 4:
        return False
    return p[3] is not None and o[3] is not None and p[3] != o[3]


@dataclass
class LayerResult:
    """Result of one layer of a layered comparison."""

    name: str
    status: str
    """'same', 'differs', or 'skipped'."""
    message: str = ""
    details: dict = dataclass_field(default_factory=dict)


@dataclass
class AlignmentStep:
    """One step of aligning the 'other' measure sequence with the 'preferred' one."""

    operation: str
    """One of OPERATIONS (from the point of view of 'other')."""
    preferred: Tuple[int, ...]
    """Counts of the involved preferred measures (empty for 'delete')."""
    other: Tuple[int, ...]
    """Counts of the involved other measures (empty for 'insert')."""
    preferred_lengths: Tuple[Optional[float], ...] = ()
    other_lengths: Tuple[Optional[float], ...] = ()
    preferred_time_signatures: Tuple[Optional[str], ...] = ()
    other_time_signatures: Tuple[Optional[str], ...] = ()

    def describe(self) -> str:
        def length(lengths) -> str:
            # measures without a defined length are described by their count only
            return f" ({lengths[0]:g}q)" if lengths and lengths[0] is not None else ""

        p = "+".join(str(c) for c in self.preferred)
        o = "+".join(str(c) for c in self.other)
        if self.operation == "match":
            return f"preferred {p} = other {o}"
        if self.operation == "change_length":
            return (
                f"preferred {p}{length(self.preferred_lengths)} ≠ other {o}{length(self.other_lengths)}: "
                f"different length"
            )
        if self.operation == "change_time_signature":
            return (
                f"preferred {p} ({self.preferred_time_signatures[0]}) ≠ other {o} "
                f"({self.other_time_signatures[0]}): different time signature"
            )
        if self.operation == "join":
            return f"other {o} would need to be joined to correspond to preferred {p}"
        if self.operation == "split":
            return f"other {o} would need to be split to correspond to preferred {p}"
        if self.operation == "insert":
            return f"preferred {p}{length(self.preferred_lengths)} has no counterpart in other"
        if self.operation == "delete":
            return (
                f"other {o}{length(self.other_lengths)} has no counterpart in preferred"
            )
        return f"{self.operation}: preferred {p}, other {o}"


def align_measure_sequences(
    preferred: Sequence[tuple],
    other: Sequence[tuple],
    gap_cost: float = 1.0,
    change_cost: float = 1.0,
    join_split_cost: float = 0.5,
) -> List[AlignmentStep]:
    """Aligns two sequences of (count, actual_length, time_signature) or (count, actual_length, time_signature,
    number) tuples with an edit distance that, besides matches, changes of length or time signature, insertions and
    deletions, allows for joining two 'other' measures or splitting one 'other' measure when their lengths add up.
    See OPERATIONS.

    Lengths and time signatures are compared only where both sides define them. Among all alignments with the
    lowest cost, the one is chosen in which the fewest paired measures have different numbers. This decides where
    the edits are placed when the lengths cannot, e.g., when all measures have the same length or when one side
    does not define any lengths. Where neither lengths nor numbers decide (e.g., a missing measure among measures of
    equal length whose numbers are offset on one side), the position of an edit within the run of equal measures
    is arbitrary.

    The computation takes time proportional to the product of the two lengths.
    """
    n, m = len(preferred), len(other)
    INF = float("inf")
    # each cell holds (edit cost, number of paired measures with different numbers); the second is the tie-breaker
    cost = [[(INF, 0)] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = (0.0, 0)

    def better(new: Tuple[float, int], old: Tuple[float, int]) -> bool:
        if new[0] < old[0] - _EPSILON:
            return True
        return abs(new[0] - old[0]) <= _EPSILON and new[1] < old[1]

    for i in range(n + 1):
        for j in range(m + 1):
            c, d = cost[i][j]
            if c == INF:
                continue
            candidates = []
            if i < n and j < m:
                same = _same_measure(preferred[i], other[j])
                candidates.append(
                    (
                        i + 1,
                        j + 1,
                        (
                            c + (0.0 if same else change_cost),
                            d + _numbers_differ(preferred[i], other[j]),
                        ),
                        "match" if same else _change_operation(preferred[i], other[j]),
                    )
                )
            if i < n:
                candidates.append((i + 1, j, (c + gap_cost, d), "insert"))
            if j < m:
                candidates.append((i, j + 1, (c + gap_cost, d), "delete"))
            if (
                i < n
                and j + 1 < m
                and None not in (preferred[i][1], other[j][1], other[j + 1][1])
            ):
                if _lengths_equal(preferred[i][1], other[j][1] + other[j + 1][1]):
                    candidates.append((i + 1, j + 2, (c + join_split_cost, d), "join"))
            if (
                i + 1 < n
                and j < m
                and None not in (preferred[i][1], preferred[i + 1][1], other[j][1])
            ):
                if _lengths_equal(preferred[i][1] + preferred[i + 1][1], other[j][1]):
                    candidates.append((i + 2, j + 1, (c + join_split_cost, d), "split"))
            for ni, nj, nc, op in candidates:
                if better(nc, cost[ni][nj]):
                    cost[ni][nj] = nc
                    back[ni][nj] = (i, j, op)
    steps = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj, op = back[i][j]
        p_items, o_items = preferred[pi:i], other[pj:j]
        steps.append(
            AlignmentStep(
                operation=op,
                preferred=tuple(item[0] for item in p_items),
                other=tuple(item[0] for item in o_items),
                preferred_lengths=tuple(item[1] for item in p_items),
                other_lengths=tuple(item[1] for item in o_items),
                preferred_time_signatures=tuple(item[2] for item in p_items),
                other_time_signatures=tuple(item[2] for item in o_items),
            )
        )
        i, j = pi, pj
    return steps[::-1]


@dataclass
class ComparisonReport:
    """Result of :func:`compare_layered`."""

    preferred: MeasureMap
    other: MeasureMap
    layers: Dict[str, LayerResult]
    """The results of the layers 'count', 'fields', 'unfolded', and 'aligned', in this order."""
    verdict: str
    """One of VERDICTS."""
    alignment: List[AlignmentStep] = dataclass_field(default_factory=list)
    alignment_basis: Optional[str] = None
    """'folded' or 'unfolded': which sequences the alignment refers to."""
    preferred_name: str = "preferred"
    other_name: str = "other"

    def summary(self) -> dict:
        """One flat dictionary per comparison, convenient for assembling corpus-level tables. Keys:

        * preferred, other: the names of the two MeasureMaps
        * verdict: one of VERDICTS
        * n_preferred, n_other: numbers of measures
        * duration_preferred, duration_other: total durations in quarter notes (None if lengths are missing)
        * lengths_compared: False if one side does not define any measure lengths
        * compared_fields: fields that both sides define and that were compared measure by measure
          (empty if the numbers of measures differ)
        * undefined_fields: fields that could not be compared because one side does not define them
        * differing_fields: the compared fields with at least one difference
        * number_offset: the difference other.number - preferred.number if it is the same for all measures
        * n_preferred_unfolded, n_other_unfolded: numbers of measures of the play-throughs (None if not computed)
        * n_join, n_split, n_change_length, n_change_time_signature, n_insert, n_delete: how often each operation
          occurs in the alignment (None if no alignment was computed)
        * message: the messages of all layers
        """
        count = self.layers["count"].details
        result = dict(
            preferred=self.preferred_name,
            other=self.other_name,
            verdict=self.verdict,
            n_preferred=count["n_preferred"],
            n_other=count["n_other"],
            duration_preferred=count["duration_preferred"],
            duration_other=count["duration_other"],
            lengths_compared=count["lengths_compared"],
        )
        fields_details = self.layers["fields"].details
        for key in ("compared", "undefined", "differing"):
            result[f"{key}_fields"] = ", ".join(fields_details.get(key, []))
        result["number_offset"] = fields_details.get("number_offset")
        unfolded = self.layers["unfolded"].details
        result["n_preferred_unfolded"] = unfolded.get("n_preferred")
        result["n_other_unfolded"] = unfolded.get("n_other")
        ops = [step.operation for step in self.alignment]
        for op in OPERATIONS[1:]:
            result[f"n_{op}"] = ops.count(op) if self.alignment else None
        result["message"] = " | ".join(
            f"{layer.name}: {layer.message}"
            for layer in self.layers.values()
            if layer.message
        )
        return result

    def measure_table(self) -> "pd.DataFrame":
        """Measure-by-measure juxtaposition that covers all measures of both sides.

        * If an alignment was computed, the rows follow its steps. A join or split occupies one row in which the
          values of the two joined measures are separated by '+'.
        * If the MeasureMaps are the same when unfolded, the rows follow the two play-throughs, so counts recur.
        * Otherwise both sides have the same number of measures and the rows pair them by position.

        The count columns contain strings (e.g., '11+12' for a split, '' for a measure without counterpart). The
        column 'differing' lists the fields in which the two sides of a row differ.
        """
        import pandas as pd

        p_by_count = {m.count: m for m in self.preferred}
        o_by_count = {m.count: m for m in self.other}

        def cell(values: list):
            if len(values) == 1:
                return values[0]
            return "+".join(str(v) for v in values) if values else None

        def row(operation: str, p_counts: Sequence[int], o_counts: Sequence[int]):
            result = dict(
                operation=operation,
                differing="",
                preferred_count="+".join(str(c) for c in p_counts),
                other_count="+".join(str(c) for c in o_counts),
            )
            differing = []
            for fld in LAYERED_FIELDS:
                if fld == "actual_length":
                    p_values = [_actual_length(p_by_count[c]) for c in p_counts]
                    o_values = [_actual_length(o_by_count[c]) for c in o_counts]
                else:
                    p_values = [getattr(p_by_count[c], fld) for c in p_counts]
                    o_values = [getattr(o_by_count[c], fld) for c in o_counts]
                result[f"preferred_{fld}"] = cell(p_values)
                result[f"other_{fld}"] = cell(o_values)
                if len(p_values) == 1 and len(o_values) == 1:
                    pv, ov = p_values[0], o_values[0]
                    if pv is not None and ov is not None and not _values_equal(pv, ov):
                        differing.append(fld)
            result["differing"] = ", ".join(differing)
            return result

        unfolded = self.layers["unfolded"]
        if self.alignment:
            rows = [
                row(step.operation, step.preferred, step.other)
                for step in self.alignment
            ]
        elif unfolded.status == "same":
            rows = [
                row("match", [p], [o])
                for p, o in zip(
                    unfolded.details["preferred_sequence"],
                    unfolded.details["other_sequence"],
                )
            ]
        else:
            rows = [
                row("match", [p.count], [o.count])
                for p, o in zip(self.preferred, self.other)
            ]
        return pd.DataFrame(rows)

    def to_text(self) -> str:
        """The verdict, one line per layer, and the steps of the alignment other than matches."""
        lines = [
            f"{self.preferred_name} (preferred) vs. {self.other_name} (other): {self.verdict.upper()}"
        ]
        for layer in self.layers.values():
            lines.append(f"  [{layer.status:>7}] {layer.name}: {layer.message}")
        if self.alignment:
            lines.append(f"  Alignment of the {self.alignment_basis} sequences:")
            for step in self.alignment:
                if step.operation != "match":
                    lines.append(f"    - {step.describe()}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_text()


def _describe_mismatches(counts: List[int], limit: int = 8) -> str:
    shown = ", ".join(str(c) for c in counts[:limit])
    return shown + (", ..." if len(counts) > limit else "")


def _offset_segments(p_entries, o_entries) -> List[Tuple[int, int, int]]:
    """Run-length encodes the differences other.number - preferred.number as (first_count, last_count, offset)
    segments, skipping measures without a number on either side and leaving out segments with offset 0.
    """
    segments = []
    for p, o in zip(p_entries, o_entries):
        if p.number is None or o.number is None:
            continue
        offset = o.number - p.number
        if segments and segments[-1][2] == offset:
            segments[-1][1] = p.count
        else:
            segments.append([p.count, p.count, offset])
    return [tuple(seg) for seg in segments if seg[2] != 0]


def _item(measure) -> tuple:
    return (
        measure.count,
        _actual_length(measure),
        measure.time_signature,
        measure.number,
    )


def _compare_counts(p_entries, o_entries) -> LayerResult:
    """Layer 1: numbers of measures and total durations."""
    n_p, n_o = len(p_entries), len(o_entries)
    p_lengths = [_actual_length(m) for m in p_entries]
    o_lengths = [_actual_length(m) for m in o_entries]
    dur_p = sum(p_lengths) if None not in p_lengths else None
    dur_o = sum(o_lengths) if None not in o_lengths else None
    without_lengths = [
        name
        for name, lengths in (("preferred", p_lengths), ("other", o_lengths))
        if all(length is None for length in lengths)
    ]
    if dur_p is not None and dur_o is not None:
        duration_msg = f"; total durations {dur_p:g}q vs. {dur_o:g}q"
    elif without_lengths:
        duration_msg = (
            f"; {' and '.join(without_lengths)} without measure lengths, which are therefore "
            f"not compared"
        )
    else:
        duration_msg = ""
    return LayerResult(
        "count",
        "same" if n_p == n_o else "differs",
        f"{n_p} vs. {n_o} measures{duration_msg}",
        dict(
            n_preferred=n_p,
            n_other=n_o,
            duration_preferred=dur_p,
            duration_other=dur_o,
            lengths_compared=not without_lengths,
        ),
    )


def _compare_fields(p_entries, o_entries, fields: Sequence[str]) -> LayerResult:
    """Layer 2: field-wise comparison of two MeasureMaps that have the same number of measures."""
    p_lengths = [_actual_length(m) for m in p_entries]
    o_lengths = [_actual_length(m) for m in o_entries]
    mismatches: Dict[str, List[int]] = {}
    compared: List[str] = []
    undefined: List[str] = []
    # the structural fields decide about the verdict and are therefore always compared
    for fld in dict.fromkeys((*fields, *STRUCTURAL_FIELDS)):
        if fld == "actual_length":
            p_values, o_values = p_lengths, o_lengths
        else:
            p_values = [getattr(m, fld) for m in p_entries]
            o_values = [getattr(m, fld) for m in o_entries]
        if all(v is None for v in p_values) or all(v is None for v in o_values):
            undefined.append(fld)
            continue
        compared.append(fld)
        differing = [
            p.count
            for p, pv, ov in zip(p_entries, p_values, o_values)
            if pv is not None and ov is not None and not _values_equal(pv, ov)
        ]
        if differing:
            mismatches[fld] = differing
    details = dict(compared=compared, undefined=undefined, mismatches=mismatches)
    messages = []
    if "number" in mismatches:
        segments = _offset_segments(p_entries, o_entries)
        details["number_offsets"] = segments
        if len(segments) == 1 and segments[0][:2] == (
            p_entries[0].count,
            p_entries[-1].count,
        ):
            details["number_offset"] = segments[0][2]
        messages.append(
            "measure numbers offset by "
            + ", ".join(
                f"{off:+d} in {a}–{b}" if a != b else f"{off:+d} in {a}"
                for a, b, off in segments
            )
        )
        if "name" in mismatches and all(
            m.name is None or m.name == str(m.number) for m in p_entries + o_entries
        ):
            # names merely reflect the numbers
            del mismatches["name"]
    if "qstamp" in mismatches and None not in p_lengths and None not in o_lengths:
        # qstamps that differ only because of preceding length differences are not reported separately
        explained, p_cum, o_cum = [], 0.0, 0.0
        for p, o, pl, ol in zip(p_entries, o_entries, p_lengths, o_lengths):
            if (
                p.count in mismatches["qstamp"]
                and p.qstamp is not None
                and o.qstamp is not None
            ):
                if _lengths_equal(p.qstamp - o.qstamp, p_cum - o_cum):
                    explained.append(p.count)
            p_cum, o_cum = p_cum + pl, o_cum + ol
        remaining = [c for c in mismatches["qstamp"] if c not in explained]
        details["qstamp_explained_by_lengths"] = explained
        if remaining:
            mismatches["qstamp"] = remaining
        else:
            del mismatches["qstamp"]
    details["differing"] = list(mismatches)
    for fld, counts in mismatches.items():
        if fld == "number":
            continue
        messages.append(
            f"{fld} differs in {len(counts)} measure(s) ({_describe_mismatches(counts)})"
        )
    n_fields = len(compared) + len(undefined)
    if not compared:
        messages.append("no field is defined on both sides")
    else:
        if not mismatches:
            messages.append(
                f"the {len(compared)} of {n_fields} fields defined on both sides are identical"
            )
        if undefined:
            messages.append(f"not compared: {', '.join(undefined)}")
    return LayerResult(
        "fields", "differs" if mismatches else "same", "; ".join(messages), details
    )


def _is_join_split_only(alignment: List[AlignmentStep]) -> bool:
    return all(step.operation in ("match", "join", "split") for step in alignment)


def compare_layered(
    preferred: MeasureMap | Path | str | dict,
    other: MeasureMap | Path | str | dict,
    fields: Iterable[str] = LAYERED_FIELDS,
    preferred_name: Optional[str] = None,
    other_name: Optional[str] = None,
) -> ComparisonReport:
    """Compares two MeasureMaps layer by layer and returns a ComparisonReport.

    The layered comparison answers increasingly specific questions, stopping as soon as a question cannot be
    answered positively, and records the answer to each of them:

    1. count: Do both sides have the same number of measures?
    2. fields: If yes: which of the fields defined on both sides are identical, measure by measure? (actual
       lengths, time signatures, numbering including offsets, repeats, voltas, ...)
    3. unfolded: If the counts or the repeats differ: do the measure sequences match once both sides have been
       unfolded, i.e., repeats written out (see :func:`unfold`)? This catches the frequent case that one edition
       uses repeat signs where the other writes the music out.
    4. aligned: If still no match: which joins, splits, insertions, deletions, and changes of length or time
       signature turn the other sequence into the preferred one (see OPERATIONS)?

    Fields that one side does not define are not compared and do not count as differences. In particular, a
    MeasureMap without measure lengths can be compared with one that has them.

    Args:
        preferred: The MeasureMap considered as reference.
        other: The MeasureMap to be compared with the reference.
        fields:
            The fields to be compared in layer 2, a subset of LAYERED_FIELDS. 'actual_length' and 'time_signature'
            are always compared because the verdict depends on them.
        preferred_name, other_name: Labels used in the report. Default to the file names if paths are passed.

    Returns:
        A ComparisonReport with the verdict (one of VERDICTS), the result of each layer, and the alignment if one
        was computed. Its methods summary(), measure_table() and to_text() present the result as a flat
        dictionary, a measure-by-measure table, and a text.

    Raises:
        ValueError: If fields contains a name that is not in LAYERED_FIELDS.
    """
    fields = list(fields)
    unknown = [fld for fld in fields if fld not in LAYERED_FIELDS]
    if unknown:
        raise ValueError(
            f"Unknown field(s) {unknown}. Choose from {', '.join(LAYERED_FIELDS)}."
        )
    if preferred_name is None:
        preferred_name = (
            Path(preferred).name if isinstance(preferred, (str, Path)) else "preferred"
        )
    if other_name is None:
        other_name = Path(other).name if isinstance(other, (str, Path)) else "other"
    p_mm = _prepare(resolve_measure_map_argument(preferred))
    o_mm = _prepare(resolve_measure_map_argument(other))
    p_entries, o_entries = list(p_mm), list(o_mm)
    layers: Dict[str, LayerResult] = {}

    # layer 1: count & total duration
    layers["count"] = _compare_counts(p_entries, o_entries)
    same_count = layers["count"].status == "same"

    # layer 2: field-wise comparison
    structure_same, repeats_differ = False, False
    if same_count:
        layers["fields"] = _compare_fields(p_entries, o_entries, fields)
        mismatches = layers["fields"].details["mismatches"]
        structure_same = not any(fld in mismatches for fld in STRUCTURAL_FIELDS)
        repeats_differ = any(fld in mismatches for fld in REPEAT_FIELDS)
    else:
        layers["fields"] = LayerResult("fields", "skipped", "", {})

    # layer 3: unfolding, if at least one side has repeats
    p_seq, o_seq = unfold(p_mm), unfold(o_mm)
    has_repeats = p_seq != [m.count for m in p_entries] or o_seq != [
        m.count for m in o_entries
    ]
    unfolded_same = False
    p_by_count = {m.count: m for m in p_entries}
    o_by_count = {m.count: m for m in o_entries}
    p_unfolded = [_item(p_by_count[c]) for c in p_seq]
    o_unfolded = [_item(o_by_count[c]) for c in o_seq]
    if has_repeats and (not same_count or repeats_differ):
        unfolded_same = len(p_unfolded) == len(o_unfolded) and all(
            _same_measure(p, o) for p, o in zip(p_unfolded, o_unfolded)
        )
        message = f"{len(p_seq)} vs. {len(o_seq)} measures when unfolded"
        if unfolded_same:
            message += " and identical"
            if len(p_entries) > len(o_entries):
                message += " (preferred writes out what other repeats)"
            elif len(o_entries) > len(p_entries):
                message += " (other writes out what preferred repeats)"
            if not layers["count"].details["lengths_compared"]:
                message += "; without measure lengths, this rests on the numbers of measures alone"
        layers["unfolded"] = LayerResult(
            "unfolded",
            "same" if unfolded_same else "differs",
            message,
            dict(
                n_preferred=len(p_seq),
                n_other=len(o_seq),
                preferred_sequence=p_seq,
                other_sequence=o_seq,
            ),
        )
    else:
        layers["unfolded"] = LayerResult("unfolded", "skipped", "", {})

    # layer 4: alignment
    alignment, basis = [], None
    if not (same_count and structure_same) and not unfolded_same:
        candidates = [
            (
                "folded",
                align_measure_sequences(
                    [_item(m) for m in p_entries], [_item(m) for m in o_entries]
                ),
            )
        ]
        if has_repeats:
            candidates.append(
                ("unfolded", align_measure_sequences(p_unfolded, o_unfolded))
            )

        def n_edits(steps: List[AlignmentStep]) -> int:
            return sum(step.operation != "match" for step in steps)

        # an alignment that needs joins and splits only is preferred, then the one with fewer edits, then the
        # unfolded one
        basis, alignment = min(
            candidates,
            key=lambda c: (
                not _is_join_split_only(c[1]),
                n_edits(c[1]),
                c[0] != "unfolded",
            ),
        )
        ops = [step.operation for step in alignment if step.operation != "match"]
        counts = {op: ops.count(op) for op in dict.fromkeys(ops)}
        layers["aligned"] = LayerResult(
            "aligned",
            "same" if not ops else "differs",
            f"{basis} sequences: "
            + (
                ", ".join(f"{n}× {op}" for op, n in counts.items()) or "no edits needed"
            ),
            dict(
                basis=basis,
                operations=counts,
                n_edits={name: n_edits(steps) for name, steps in candidates},
            ),
        )
    else:
        layers["aligned"] = LayerResult("aligned", "skipped", "", {})

    # verdict
    if same_count and not layers["fields"].details["compared"]:
        verdict = "same_count"
    elif same_count and layers["fields"].status == "same":
        verdict = "identical"
    elif same_count and structure_same:
        verdict = "same_measures"
    elif unfolded_same:
        verdict = "same_when_unfolded"
    elif alignment and _is_join_split_only(alignment):
        verdict = "alignable"
    elif same_count:
        verdict = "same_count_different_measures"
    else:
        verdict = "different"
    return ComparisonReport(
        preferred=p_mm,
        other=o_mm,
        layers=layers,
        verdict=verdict,
        alignment=alignment,
        alignment_basis=basis,
        preferred_name=preferred_name,
        other_name=other_name,
    )


def _default_names(pairs: Sequence[tuple]) -> List[Tuple[str, str]]:
    """Names for the two sides of each pair: for files, the path relative to the directory that all files have in
    common (so that equally named files in different folders stay distinguishable), otherwise 'preferred_<i>' and
    'other_<i>'.
    """
    paths = [
        Path(item).resolve()
        for pair in pairs
        for item in pair
        if isinstance(item, (str, Path))
    ]
    parents = {path.parent for path in paths}
    if len(parents) > 1:
        common = Path(os.path.commonpath([str(parent) for parent in parents]))
    else:
        common = None

    def name(item, side: str, i: int) -> str:
        if not isinstance(item, (str, Path)):
            return f"{side}_{i}"
        path = Path(item).resolve()
        return path.name if common is None else path.relative_to(common).as_posix()

    return [
        (name(p, "preferred", i), name(o, "other", i))
        for i, (p, o) in enumerate(pairs, 1)
    ]


def _file_stem(name: str) -> str:
    """Turns the name of a MeasureMap into a part of a file name."""
    for ext in (".mm.json", ".json"):
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_") or "measure_map"


def compare_pairs(
    pairs: Iterable[Tuple[MeasureMap | Path | str, MeasureMap | Path | str]],
    names: Optional[Iterable[Tuple[str, str]]] = None,
    output_directory: Optional[Path | str] = None,
    **kwargs,
) -> Tuple["pd.DataFrame", List[Optional[ComparisonReport]]]:
    """Runs :func:`compare_layered` on each (preferred, other) pair.

    Args:
        pairs: (preferred, other) pairs of MeasureMaps or paths to MeasureMap files.
        names:
            One (preferred_name, other_name) pair for each pair, used in the summary, the reports and the file
            names. By default, files are named by their path relative to the directory they have in common, and
            MeasureMap objects 'preferred_<i>' and 'other_<i>'.
        output_directory:
            If given, 'comparison_summary.tsv' is written into it and, for each pair that is not identical,
            '<preferred>_vs_<other>.tsv' (:meth:`ComparisonReport.measure_table`) and '.txt'
            (:meth:`ComparisonReport.to_text`). Characters that are unfit for file names are replaced with '_', and
            a number is appended where two pairs would result in the same file name.
        **kwargs: Passed on to :func:`compare_layered`.

    Returns:
        A summary table with one row per pair (see :meth:`ComparisonReport.summary`) and the list of reports. A
        pair that could not be compared (e.g., because a file is missing or invalid) has the verdict 'error', the
        error in the column 'message', and None in the place of its report. If a file could not be written for a
        pair, the column 'output_error' says why.

    Raises:
        ValueError: If names does not have as many elements as pairs.
    """
    import pandas as pd

    pairs = list(pairs)
    names = _default_names(pairs) if names is None else list(names)
    if len(names) != len(pairs):
        raise ValueError(f"Got {len(names)} names for {len(pairs)} pairs.")
    reports, rows = [], []
    for (preferred, other), (p_name, o_name) in zip(pairs, names):
        try:
            report = compare_layered(
                preferred, other, preferred_name=p_name, other_name=o_name, **kwargs
            )
        except Exception as e:
            module_logger.warning(
                f"Comparing {p_name} with {o_name} failed: {e!r}", exc_info=True
            )
            rows.append(
                dict(preferred=p_name, other=o_name, verdict="error", message=repr(e))
            )
            reports.append(None)
            continue
        reports.append(report)
        rows.append(report.summary())
    if output_directory is not None:
        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        used_stems = set()
        for report, row in zip(reports, rows):
            if report is None or report.verdict == "identical":
                continue
            base = f"{_file_stem(report.preferred_name)}_vs_{_file_stem(report.other_name)}"
            stem, n = base, 1
            while stem.lower() in used_stems:
                n += 1
                stem = f"{base}_{n}"
            used_stems.add(stem.lower())
            try:
                report.measure_table().to_csv(
                    output_directory / f"{stem}.tsv", sep="\t", index=False
                )
                (output_directory / f"{stem}.txt").write_text(
                    report.to_text() + "\n", encoding="utf-8"
                )
            except OSError as e:
                module_logger.warning(f"Writing the report {stem} failed: {e!r}")
                row["output_error"] = repr(e)
    summary = pd.DataFrame(rows)
    if output_directory is not None:
        summary.to_csv(
            output_directory / "comparison_summary.tsv", sep="\t", index=False
        )
    return summary, reports


# endregion layered comparison
