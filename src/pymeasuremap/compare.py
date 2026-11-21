"""Comparing MeasureMaps pertaining two the same music."""

import logging
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


# region layered comparison
#
# The layered comparison answers increasingly specific questions about two MeasureMaps, stopping as soon as a
# question cannot be answered positively, and records the answer to each of them:
#
#   1. count:    Do both sides have the same number of measures?
#   2. fields:   If yes: which of the fields defined on both sides are identical, measure by measure?
#                (actual lengths, time signatures, numbering incl. constant offsets, repeats, voltas, ...)
#   3. unfolded: If the counts or the repeat structures differ: do the measure sequences match once both sides
#                have been unfolded (i.e., repeats written out)? This catches the frequent case that one edition
#                uses repeat signs where the other writes the music out.
#   4. aligned:  If still no match: which joins, splits, insertions, deletions, and length changes turn the other
#                sequence into the preferred one?
#
# The result is a ComparisonReport offering a one-row summary (for corpus-level tables), a measure-by-measure table,
# and a human-readable text.

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
    "same_measures",
    "same_count_different_measures",
    "same_when_unfolded",
    "alignable",
    "different",
)
"""Possible verdicts, from the most to the least similar:

* identical: same number of measures, all fields defined on both sides are identical.
* same_measures: same number of measures with the same lengths and time signatures; other fields (e.g., numbering
  or repeat signs) differ.
* same_count_different_measures: same number of measures, but some lengths or time signatures differ.
* same_when_unfolded: the numbers of measures differ, but the unfolded sequences of measures are identical.
* alignable: the sequences can be aligned with joins and splits only, i.e., the music has the same total duration
  but measures are segmented differently.
* different: the alignment requires insertions, deletions, or changes of measure lengths.
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
    number corresponds to the volta number.
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
        if len(sequence) >= max_length:
            module_logger.warning(
                "Unfolding stopped because the 'next' fields seem to describe an endless loop."
            )
        return sequence
    # infer from repeat signs and voltas
    sequence, i, section_start, current_pass, repeated_ends = [], 0, 0, 1, set()
    while i < len(measures) and len(sequence) < max_length:
        measure = measures[i]
        if measure.start_repeat and i != section_start and current_pass == 1:
            section_start = i
        if measure.volta is not None and measure.volta != current_pass:
            i += 1
            continue
        sequence.append(measure.count)
        if measure.end_repeat and i not in repeated_ends:
            repeated_ends.add(i)
            i, current_pass = section_start, 2
            continue
        if measure.end_repeat or (measure.volta is not None and current_pass > 1):
            current_pass = 1
            section_start = i + 1
        i += 1
    return sequence


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
    """'match', 'change_length', 'join', 'split', 'insert', or 'delete' (from the point of view of 'other')."""
    preferred: Tuple[int, ...]
    """Counts of the involved preferred measures (empty for 'delete')."""
    other: Tuple[int, ...]
    """Counts of the involved other measures (empty for 'insert')."""
    preferred_lengths: Tuple[float, ...] = ()
    other_lengths: Tuple[float, ...] = ()

    def describe(self) -> str:
        p = "+".join(str(c) for c in self.preferred)
        o = "+".join(str(c) for c in self.other)
        if self.operation == "match":
            return f"preferred {p} = other {o}"
        if self.operation == "change_length":
            return (
                f"preferred {p} ({self.preferred_lengths[0]:g}q) ≠ other {o} ({self.other_lengths[0]:g}q): "
                f"different length"
            )
        if self.operation == "join":
            return f"other {o} would need to be joined to correspond to preferred {p}"
        if self.operation == "split":
            return f"other {o} would need to be split to correspond to preferred {p}"
        if self.operation == "insert":
            return f"preferred {p} ({self.preferred_lengths[0]:g}q) has no counterpart in other"
        if self.operation == "delete":
            return f"other {o} ({self.other_lengths[0]:g}q) has no counterpart in preferred"
        return f"{self.operation}: preferred {p}, other {o}"


def align_measure_sequences(
    preferred: Sequence[Tuple[int, Optional[float], Optional[str]]],
    other: Sequence[Tuple[int, Optional[float], Optional[str]]],
    gap_cost: float = 1.0,
    change_cost: float = 1.0,
    join_split_cost: float = 0.5,
) -> List[AlignmentStep]:
    """Aligns two sequences of (count, actual_length, time_signature) triples with an edit distance that, besides
    matches, length changes, insertions and deletions, allows for joining two 'other' measures or splitting one
    'other' measure when their lengths add up. Time signatures are compared only where both sides specify them.
    """
    n, m = len(preferred), len(other)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0

    def same(p, o) -> bool:
        if not _lengths_equal(p[1], o[1]):
            return False
        return p[2] is None or o[2] is None or p[2] == o[2]

    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c == INF:
                continue
            candidates = []
            if i < n and j < m:
                step_cost = 0.0 if same(preferred[i], other[j]) else change_cost
                candidates.append(
                    (
                        i + 1,
                        j + 1,
                        c + step_cost,
                        "match" if step_cost == 0 else "change_length",
                    )
                )
            if i < n:
                candidates.append((i + 1, j, c + gap_cost, "insert"))
            if j < m:
                candidates.append((i, j + 1, c + gap_cost, "delete"))
            if (
                i < n
                and j + 1 < m
                and None not in (preferred[i][1], other[j][1], other[j + 1][1])
            ):
                if _lengths_equal(preferred[i][1], other[j][1] + other[j + 1][1]):
                    candidates.append((i + 1, j + 2, c + join_split_cost, "join"))
            if (
                i + 1 < n
                and j < m
                and None not in (preferred[i][1], preferred[i + 1][1], other[j][1])
            ):
                if _lengths_equal(preferred[i][1] + preferred[i + 1][1], other[j][1]):
                    candidates.append((i + 2, j + 1, c + join_split_cost, "split"))
            for ni, nj, nc, op in candidates:
                if nc < cost[ni][nj] - _EPSILON:
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
    verdict: str
    alignment: List[AlignmentStep] = dataclass_field(default_factory=list)
    alignment_basis: Optional[str] = None
    """'folded' or 'unfolded': which sequences the alignment refers to."""
    preferred_name: str = "preferred"
    other_name: str = "other"

    def summary(self) -> dict:
        """One flat dictionary per comparison, convenient for assembling corpus-level tables."""
        count = self.layers["count"].details
        result = dict(
            preferred=self.preferred_name,
            other=self.other_name,
            verdict=self.verdict,
            n_preferred=count["n_preferred"],
            n_other=count["n_other"],
            duration_preferred=count["duration_preferred"],
            duration_other=count["duration_other"],
        )
        fields_layer = self.layers["fields"]
        result["differing_fields"] = ", ".join(
            fields_layer.details.get("differing", [])
        )
        result["number_offset"] = fields_layer.details.get("number_offset")
        unfolded = self.layers["unfolded"].details
        result["n_preferred_unfolded"] = unfolded.get("n_preferred")
        result["n_other_unfolded"] = unfolded.get("n_other")
        ops = [step.operation for step in self.alignment if step.operation != "match"]
        for op in ("join", "split", "change_length", "insert", "delete"):
            result[f"n_{op}"] = ops.count(op) if self.alignment else None
        result["message"] = " | ".join(
            f"{layer.name}: {layer.message}"
            for layer in self.layers.values()
            if layer.message
        )
        return result

    def measure_table(self) -> "pd.DataFrame":
        """Measure-by-measure juxtaposition. If both sides have the same number of measures, the rows are paired by
        position; otherwise, they follow the alignment (where counts may repeat for unfolded sequences).
        """
        import pandas as pd

        p_by_count = {m.count: m for m in _prepare(self.preferred)}
        o_by_count = {m.count: m for m in _prepare(self.other)}
        rows = []
        if self.alignment:
            for step in self.alignment:
                row = dict(
                    operation=step.operation,
                    preferred_count="+".join(str(c) for c in step.preferred),
                    other_count="+".join(str(c) for c in step.other),
                )
                for side, counts, lookup in (
                    ("preferred", step.preferred, p_by_count),
                    ("other", step.other, o_by_count),
                ):
                    for fld in (
                        "number",
                        "name",
                        "time_signature",
                        "actual_length",
                        *REPEAT_FIELDS[:3],
                    ):
                        values = [getattr(lookup[c], fld) for c in counts]
                        row[f"{side}_{fld}"] = (
                            values[0] if len(values) == 1 else (values or None)
                        )
                rows.append(row)
            return pd.DataFrame(rows)
        for p, o in zip(_prepare(self.preferred), _prepare(self.other)):
            row = dict(preferred_count=p.count, other_count=o.count)
            differing = []
            for fld in LAYERED_FIELDS:
                pv, ov = getattr(p, fld), getattr(o, fld)
                row[f"preferred_{fld}"], row[f"other_{fld}"] = pv, ov
                if pv is not None and ov is not None and not _values_equal(pv, ov):
                    differing.append(fld)
            row["differing"] = ", ".join(differing)
            row["operation"] = "differs" if differing else "match"
            rows.append(row)
        df = pd.DataFrame(rows)
        return df[
            ["operation", "differing"]
            + [c for c in df.columns if c not in ("operation", "differing")]
        ]

    def to_text(self) -> str:
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


def _repeat_signature(mm: MeasureMap) -> List[tuple]:
    return [
        (m.count, bool(m.start_repeat), bool(m.end_repeat), m.volta)
        for m in mm
        if m.start_repeat or m.end_repeat or m.volta
    ]


def compare_layered(
    preferred: MeasureMap | Path | str | dict,
    other: MeasureMap | Path | str | dict,
    fields: Iterable[str] = LAYERED_FIELDS,
    preferred_name: Optional[str] = None,
    other_name: Optional[str] = None,
) -> ComparisonReport:
    """Compares two MeasureMaps layer by layer (see the module comment above) and returns a ComparisonReport.

    Args:
        preferred: The MeasureMap considered as reference.
        other: The MeasureMap to be compared with the reference.
        fields: The fields to be compared in layer 2 if both sides have the same number of measures.
        preferred_name, other_name: Labels used in the report. Default to the file names if paths are passed.
    """
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
    n_p, n_o = len(p_entries), len(o_entries)
    p_lengths = [_actual_length(m) for m in p_entries]
    o_lengths = [_actual_length(m) for m in o_entries]
    dur_p = sum(p_lengths) if None not in p_lengths else None
    dur_o = sum(o_lengths) if None not in o_lengths else None
    count_details = dict(
        n_preferred=n_p, n_other=n_o, duration_preferred=dur_p, duration_other=dur_o
    )
    same_count = n_p == n_o
    duration_msg = (
        f"; total durations {dur_p:g}q vs. {dur_o:g}q"
        if dur_p is not None and dur_o is not None
        else ""
    )
    layers["count"] = LayerResult(
        "count",
        "same" if same_count else "differs",
        f"{n_p} vs. {n_o} measures{duration_msg}",
        count_details,
    )

    # layer 2: field-wise comparison
    structure_same = False
    repeats_differ = _repeat_signature(p_mm) != _repeat_signature(o_mm)
    if same_count:
        mismatches: Dict[str, List[int]] = {}
        undefined: List[str] = []
        for fld in fields:
            p_values = [getattr(m, fld) for m in p_entries]
            o_values = [getattr(m, fld) for m in o_entries]
            if fld == "actual_length":
                p_values, o_values = p_lengths, o_lengths
            if all(v is None for v in p_values) or all(v is None for v in o_values):
                undefined.append(fld)
                continue
            differing = [
                p.count
                for p, pv, ov in zip(p_entries, p_values, o_values)
                if pv is not None and ov is not None and not _values_equal(pv, ov)
            ]
            if differing:
                mismatches[fld] = differing
        details = dict(
            differing=list(mismatches), mismatches=mismatches, undefined=undefined
        )
        messages = []
        if "number" in mismatches:
            segments = _offset_segments(p_entries, o_entries)
            details["number_offsets"] = segments
            if len(segments) == 1:
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
                details["differing"] = list(mismatches)
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
        structure_same = not any(fld in mismatches for fld in STRUCTURAL_FIELDS)
        repeats_differ = any(fld in mismatches for fld in REPEAT_FIELDS)
        layers["fields"] = LayerResult(
            "fields",
            "differs" if mismatches else "same",
            "; ".join(messages) if messages else "all compared fields identical",
            details,
        )
    else:
        layers["fields"] = LayerResult("fields", "skipped", "", {})

    # layer 3: unfolding
    unfolded_same = False
    p_seq, o_seq = None, None
    if not same_count or repeats_differ:
        p_seq, o_seq = unfold(p_mm), unfold(o_mm)
        p_by_count = {m.count: m for m in p_entries}
        o_by_count = {m.count: m for m in o_entries}
        p_unfolded = [
            (c, _actual_length(p_by_count[c]), p_by_count[c].time_signature)
            for c in p_seq
        ]
        o_unfolded = [
            (c, _actual_length(o_by_count[c]), o_by_count[c].time_signature)
            for c in o_seq
        ]
        unfolded_same = len(p_unfolded) == len(o_unfolded) and all(
            _lengths_equal(p[1], o[1])
            and (p[2] is None or o[2] is None or p[2] == o[2])
            for p, o in zip(p_unfolded, o_unfolded)
        )
        written_out = []
        if unfolded_same and not same_count:
            if n_p > n_o:
                written_out.append("preferred writes out what other repeats")
            elif n_o > n_p:
                written_out.append("other writes out what preferred repeats")
        message = f"{len(p_seq)} vs. {len(o_seq)} measures when unfolded" + (
            f" and identical ({written_out[0]})"
            if written_out
            else (" and identical" if unfolded_same else "")
        )
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
        # align the folded sequences and, if available, the unfolded ones; keep the alignment with fewer edits
        # (preferring the unfolded one in case of a tie)
        candidates = []
        if p_seq is not None:
            p_items = [
                (c, _actual_length(p_by_count[c]), p_by_count[c].time_signature)
                for c in p_seq
            ]
            o_items = [
                (c, _actual_length(o_by_count[c]), o_by_count[c].time_signature)
                for c in o_seq
            ]
            candidates.append(("unfolded", align_measure_sequences(p_items, o_items)))
        p_items = [(m.count, _actual_length(m), m.time_signature) for m in p_entries]
        o_items = [(m.count, _actual_length(m), m.time_signature) for m in o_entries]
        candidates.append(("folded", align_measure_sequences(p_items, o_items)))
        basis, alignment = min(
            candidates, key=lambda c: sum(step.operation != "match" for step in c[1])
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
            dict(basis=basis, operations=counts),
        )
    else:
        layers["aligned"] = LayerResult("aligned", "skipped", "", {})

    # verdict
    if same_count and layers["fields"].status == "same":
        verdict = "identical"
    elif same_count and structure_same:
        verdict = "same_measures"
    elif unfolded_same:
        verdict = "same_when_unfolded"
    elif alignment and all(
        step.operation in ("match", "join", "split") for step in alignment
    ):
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


def compare_pairs(
    pairs: Iterable[Tuple[MeasureMap | Path | str, MeasureMap | Path | str]],
    names: Optional[Iterable[Tuple[str, str]]] = None,
    output_directory: Optional[Path | str] = None,
    **kwargs,
) -> Tuple["pd.DataFrame", List[ComparisonReport]]:
    """Runs :func:`compare_layered` on each (preferred, other) pair and returns a summary table (one row per pair)
    together with the reports. If output_directory is given, writes 'comparison_summary.tsv' and, for each pair that
    is not identical, '<preferred>_vs_<other>.tsv' (measure table) and '.txt' (report) into it.
    """
    import pandas as pd

    pairs = list(pairs)
    names = list(names) if names is not None else [(None, None)] * len(pairs)
    reports, rows = [], []
    for (preferred, other), (p_name, o_name) in zip(pairs, names):
        try:
            report = compare_layered(
                preferred, other, preferred_name=p_name, other_name=o_name, **kwargs
            )
        except Exception as e:
            module_logger.warning(f"Comparing {preferred} with {other} failed: {e!r}")
            rows.append(
                dict(
                    preferred=p_name or str(preferred),
                    other=o_name or str(other),
                    verdict="error",
                    message=repr(e),
                )
            )
            reports.append(None)
            continue
        reports.append(report)
        rows.append(report.summary())
    summary = pd.DataFrame(rows)
    if output_directory is not None:
        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)
        summary.to_csv(
            output_directory / "comparison_summary.tsv", sep="\t", index=False
        )
        for report in reports:
            if report is None or report.verdict == "identical":
                continue
            stem = f"{_stem(report.preferred_name)}_vs_{_stem(report.other_name)}"
            report.measure_table().to_csv(
                output_directory / f"{stem}.tsv", sep="\t", index=False
            )
            (output_directory / f"{stem}.txt").write_text(
                report.to_text() + "\n", encoding="utf-8"
            )
    return summary, reports


def _stem(name: str) -> str:
    name = Path(name).name
    for ext in (".mm.json", ".json"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


# endregion layered comparison
