"""Tests for the layered comparison (pymeasuremap.compare.compare_layered) on real measure maps.

The fixtures are measure maps of five settings from the 389 Choralgesänge (``B###``) and of their counterparts in the
Riemenschneider datasets of the aligned_bach_chorales repository (``krn_R###``, ``cap_R###``, ``xml_R###``).
See README.md in this folder for what each test makes sure and why the expected values are what they are.
"""

import csv
from pathlib import Path

import pytest

from pymeasuremap.base import MeasureMap
from pymeasuremap.compare import compare_layered, compare_pairs, unfold

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES / f"{name}.mm.json"


def load(name: str) -> MeasureMap:
    return MeasureMap.from_json_file(fixture_path(name))


def compare(preferred: str, other: str):
    return compare_layered(
        fixture_path(preferred),
        fixture_path(other),
        preferred_name=preferred,
        other_name=other,
    )


def read_expected_verdicts():
    with open(HERE / "expected_verdicts.tsv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


EXPECTED = read_expected_verdicts()


# region 1. One verdict per pair (expected_verdicts.tsv)


@pytest.mark.parametrize(
    "row", EXPECTED, ids=[f"{r['preferred']}-{r['other']}" for r in EXPECTED]
)
def test_verdict(row):
    assert compare(row["preferred"], row["other"]).verdict == row["verdict"]


def test_every_verdict_is_covered():
    from pymeasuremap.compare import VERDICTS

    # 'same_count' needs two measure maps without any field in common, which no real pair provides;
    # it is tested with synthetic measure maps in tests/test_compare_layered.py
    assert {row["verdict"] for row in EXPECTED} == set(VERDICTS) - {"same_count"}


def test_compare_pairs_reproduces_the_table(tmp_path):
    pairs = [(fixture_path(r["preferred"]), fixture_path(r["other"])) for r in EXPECTED]
    names = [(r["preferred"], r["other"]) for r in EXPECTED]
    summary, reports = compare_pairs(pairs, names=names, output_directory=tmp_path)
    assert summary.verdict.tolist() == [r["verdict"] for r in EXPECTED]
    assert (tmp_path / "comparison_summary.tsv").is_file()
    for r in EXPECTED:
        stem = f"{r['preferred']}_vs_{r['other']}"
        if r["verdict"] == "identical":
            assert not (tmp_path / f"{stem}.txt").exists()
        else:
            assert (tmp_path / f"{stem}.txt").is_file()
            assert (tmp_path / f"{stem}.tsv").is_file()


# endregion 1. One verdict per pair
# region 2. Unfolding


def test_unfold_repeat_signs_B072():
    """|: 1–6 :| |: 7–9 :| 10–13"""
    assert unfold(load("B072")) == [
        *range(1, 7),
        *range(1, 7),
        7,
        8,
        9,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
    ]


def test_unfold_written_out_krn_R087():
    """|: 1–6 :| 7–16 (the second repeat is written out as 10–12)"""
    assert unfold(load("krn_R087")) == [*range(1, 7), *range(1, 17)]


def test_unfold_split_measures_across_repeats_B205():
    """|: 1–9 :| 10–14 |: 15–19 :| 20–24, where 9+10, 14+15, 19+20 are measures split by the repeat signs."""
    assert unfold(load("B205")) == [*range(1, 10), *range(1, 20), *range(15, 25)]


# endregion 2. Unfolding
# region 3. Layers in detail


def test_identical_B072_cap():
    report = compare("B072", "cap_R087")
    assert report.layers["count"].status == "same"
    assert report.layers["fields"].status == "same"
    # neither side has voltas, so the field cannot be compared
    assert report.layers["fields"].details["undefined"] == ["volta"]
    assert report.layers["unfolded"].status == "skipped"
    assert report.layers["aligned"].status == "skipped"


def test_number_offsets_B015_cap():
    """The 389 number the anacrusis 0 and the two halves of the split measure 7 (counts 8 and 9) both 7;
    cap numbers every measure object consecutively starting from 1."""
    report = compare("B015", "cap_R359")
    fields = report.layers["fields"]
    assert fields.details["differing"] == ["number"]
    assert fields.details["number_offsets"] == [(1, 8, 1), (9, 22, 2)]
    # not a constant offset, hence no single number_offset
    assert "number_offset" not in fields.details
    assert (
        fields.message
        == "measure numbers offset by +1 in 1–8, +2 in 9–22; not compared: volta"
    )
    # names merely reflect the numbers and are therefore not reported
    assert "name" not in fields.details["differing"]


def test_length_differences_B072_xml():
    """xml has 5q instead of 4q in measures 1 and 4. All qstamps after measure 1 differ, but only as a consequence
    of these two length differences, so they are not reported as a separate mismatch."""
    report = compare("B072", "xml_R087")
    fields = report.layers["fields"]
    assert fields.details["differing"] == ["actual_length"]
    assert fields.details["mismatches"]["actual_length"] == [1, 4]
    assert fields.details["qstamp_explained_by_lengths"] == list(range(2, 14))
    assert report.alignment_basis == "folded"
    changes = [s for s in report.alignment if s.operation == "change_length"]
    assert [(s.preferred, s.preferred_lengths, s.other_lengths) for s in changes] == [
        ((1,), (4.0,), (5.0,)),
        ((4,), (4.0,), (5.0,)),
    ]


def test_written_out_repeat_B072_krn():
    report = compare("B072", "krn_R087")
    assert report.layers["count"].details["n_preferred"] == 13
    assert report.layers["count"].details["n_other"] == 16
    unfolded = report.layers["unfolded"]
    assert unfolded.status == "same"
    assert unfolded.details["n_preferred"] == unfolded.details["n_other"] == 22
    assert "other writes out what preferred repeats" in unfolded.message
    assert report.layers["aligned"].status == "skipped"


def test_split_B006_krn():
    """B006 splits krn's measure 11 (4q) into counts 11 (3q) and 12 (1q)."""
    report = compare("B006", "krn_R253")
    # neither side has repeats, so there is nothing to unfold
    assert report.layers["unfolded"].status == "skipped"
    assert report.alignment_basis == "folded"
    non_matches = [s for s in report.alignment if s.operation != "match"]
    assert len(non_matches) == 1
    step = non_matches[0]
    assert step.operation == "split"
    assert step.preferred == (11, 12) and step.other == (11,)
    assert step.preferred_lengths == (3.0, 1.0) and step.other_lengths == (4.0,)
    count = report.layers["count"].details
    assert count["duration_preferred"] == count["duration_other"] == 68
    assert report.summary()["n_split"] == 1


def test_join_across_repeats_B205_krn():
    """The repeat structures differ (see test_unfold_split_measures_across_repeats_B205). Unfolded, krn has the
    3q end of its second repeated section (count 12) followed by the 1q pickup (count 10) where the 389 have a
    single 4q measure (count 12)."""
    report = compare("B205", "krn_R327")
    assert report.alignment_basis == "unfolded"
    non_matches = [s for s in report.alignment if s.operation != "match"]
    assert [(s.operation, s.preferred, s.other) for s in non_matches] == [
        ("join", (12,), (12, 10))
    ]


def test_different_B015_krn():
    report = compare("B015", "krn_R359")
    non_matches = [s for s in report.alignment if s.operation != "match"]
    assert [(s.operation, s.preferred, s.other) for s in non_matches] == [
        ("insert", (13,), ()),
        ("change_length", (22,), (21,)),
    ]
    assert "preferred 13 (2q) has no counterpart in other" in report.to_text()


def test_compressed_map_is_identical_B015():
    """A compressed measure map omits the entries that follow from their predecessors and describes the same
    measures."""
    measure_map = load("B015")
    compressed = measure_map.compress()
    assert len(measure_map.entries) == 22
    assert [m.count for m in compressed.entries] == [1, 8, 9, 13, 22]
    report = compare_layered(measure_map, compressed)
    assert report.verdict == "identical"
    assert report.layers["count"].details["n_other"] == 22
    assert report.layers["fields"].details["undefined"] == ["volta"]
    assert report.layers["fields"].details["differing"] == []


# endregion 3. Layers in detail
# region 3b. Unfolding from repeat signs alone


@pytest.mark.parametrize(
    "name", sorted(path.name[: -len(".mm.json")] for path in FIXTURES.glob("*.mm.json"))
)
def test_unfold_from_repeat_signs_agrees_with_next(name):
    """All fixtures specify 'next'. Without it, unfold() has to infer the same play-through from the repeat signs."""
    measure_map = load(name)
    without_next = MeasureMap.from_dicts(
        [
            {key: value for key, value in vars(measure).items() if key != "next"}
            for measure in measure_map
        ]
    )
    assert all(measure.next is None for measure in without_next)
    assert unfold(without_next) == unfold(measure_map)


# endregion 3b. Unfolding from repeat signs alone


# region 4. Time signatures and the measure table


def test_time_signature_mismatch_is_not_a_length_change_B329_krn():
    """Where the 389 (2/2) and krn (4/4) measures are paired, both have 4q: the difference is one of time
    signature, not of length."""
    report = compare("B329", "krn_R179")
    assert report.verdict == "different"
    summary = report.summary()
    assert summary["n_change_length"] == 0
    assert summary["n_change_time_signature"] == 16
    assert summary["n_insert"] == 19
    assert summary["n_join"] == 1
    assert (
        "preferred 1 (2/2) ≠ other 1 (4/4): different time signature"
        in report.to_text()
    )
    assert "different length" not in report.to_text()


def test_measure_table_follows_the_play_throughs_B072_krn():
    """For 'same_when_unfolded' the table has one row per measure of the play-through (22), so that the three
    measures krn writes out (counts 10-12) are paired with the repeated counts 7-9 of the 389.
    """
    report = compare("B072", "krn_R087")
    table = report.measure_table()
    assert table.preferred_count.tolist() == [str(c) for c in unfold(load("B072"))]
    assert table.other_count.tolist() == [str(c) for c in unfold(load("krn_R087"))]
    assert len(table) == 22
    assert table.operation.unique().tolist() == ["match"]
    assert set(table.other_count) == {str(c) for c in range(1, 17)}
    written_out = table[table.other_count.isin(["10", "11", "12"])]
    assert written_out.preferred_count.tolist() == ["7", "8", "9"]
    # lengths and time signatures agree in every row
    assert not table.differing.str.contains("actual_length|time_signature").any()


# endregion 4. Time signatures and the measure table
