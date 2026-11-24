"""Tests for the layered comparison (pymeasuremap.compare) on small synthetic measure maps.

See README_compare_layered.md in this folder for what each test makes sure and why the expected values are what they
are.
"""

import csv

import pytest

from pymeasuremap.base import Measure, MeasureMap
from pymeasuremap.compare import (
    AlignmentStep,
    align_measure_sequences,
    compare_layered,
    compare_pairs,
    unfold,
)


def make_mm(actual_lengths, numbers=None, **kwargs) -> MeasureMap:
    n = len(actual_lengths)
    qstamps, q = [], 0.0
    for length in actual_lengths:
        qstamps.append(q)
        q += length
    return MeasureMap.from_array(
        count=range(1, n + 1),
        number=numbers if numbers is not None else range(1, n + 1),
        qstamp=qstamps,
        time_signature=["4/4"] * n,
        actual_length=actual_lengths,
        **kwargs,
    )


def repeated_mm():
    """Four measures, the first two of which are repeated: |: 1 2 :| 3 4"""
    return make_mm(
        [4.0] * 4,
        start_repeat=[True, False, False, False],
        end_repeat=[False, True, False, False],
    )


def written_out_mm():
    """The same music as repeated_mm() with the repeat written out: 1 2 1 2 3 4"""
    return make_mm([4.0] * 6)


# The length of a measure


def test_length_from_nominal_length_only():
    measure = Measure(count=1, nominal_length=3.0)
    assert measure.get_actual_length() == 3.0
    assert measure.get_nominal_length() == 3.0


def test_length_from_time_signature_only():
    measure = Measure(count=1, time_signature="3/4")
    assert measure.get_actual_length() == 3.0
    assert measure.get_nominal_length() == 3.0


def test_length_stated_wins():
    measure = Measure(
        count=1, time_signature="4/4", nominal_length=4.0, actual_length=1.0
    )
    assert measure.get_actual_length() == 1.0
    assert measure.get_nominal_length() == 4.0


def test_length_unknown_without_length_fields():
    measure = Measure(count=1)
    with pytest.raises(ValueError):
        measure.get_actual_length()
    with pytest.raises(ValueError):
        measure.get_nominal_length()


@pytest.mark.parametrize("time_signature", ["C", "4/0"])
def test_length_unknown_for_time_signature_that_is_no_fraction(time_signature):
    measure = Measure(count=1, time_signature=time_signature)
    with pytest.raises(ValueError, match=repr(time_signature)):
        measure.get_actual_length()
    with pytest.raises(ValueError, match=repr(time_signature)):
        measure.get_nominal_length()


def test_compare_uses_nominal_length_as_length():
    preferred = MeasureMap.from_array(count=[1, 2], nominal_length=[3.0, 3.0])
    other = MeasureMap.from_array(count=[1, 2], actual_length=[3.0, 3.0])
    report = compare_layered(preferred, other)
    assert report.verdict == "identical"
    assert report.layers["fields"].details["compared"] == ["actual_length"]
    assert "nominal_length" in report.layers["fields"].details["undefined"]
    count = report.layers["count"].details
    assert count["duration_preferred"] == 6.0
    assert count["duration_other"] == 6.0
    assert count["lengths_compared"] is True


# Unfolding


def test_unfold_infers_repeats():
    assert unfold(repeated_mm()) == [1, 2, 1, 2, 3, 4]


def test_unfold_with_next_and_voltas():
    mm = make_mm(
        [4.0] * 4,
        volta=[None, 1, 2, None],
        next=[[2, 3], [1], [4], [-1]],
    )
    assert unfold(mm) == [1, 2, 1, 3, 4]


def test_unfold_infers_voltas():
    mm = make_mm(
        [4.0] * 4,
        start_repeat=[True, False, False, False],
        end_repeat=[False, True, False, False],
        volta=[None, 1, 2, None],
    )
    assert unfold(mm) == [1, 2, 1, 3, 4]


def test_identical():
    report = compare_layered(make_mm([1.0, 4.0, 3.0]), make_mm([1.0, 4.0, 3.0]))
    assert report.verdict == "identical"
    assert report.layers["unfolded"].status == "skipped"


def test_same_measures_with_number_offset():
    report = compare_layered(
        make_mm([1.0, 4.0, 3.0], numbers=[0, 1, 2]), make_mm([1.0, 4.0, 3.0])
    )
    assert report.verdict == "same_measures"
    assert report.layers["fields"].details["number_offset"] == 1
    assert report.summary()["differing_fields"] == "number"


def test_qstamp_differences_explained_by_lengths_are_not_reported():
    report = compare_layered(make_mm([4.0, 4.0, 4.0]), make_mm([4.0, 3.0, 4.0]))
    assert report.verdict == "same_count_different_measures"
    assert report.layers["fields"].details["differing"] == ["actual_length"]
    assert report.layers["fields"].details["qstamp_explained_by_lengths"] == [3]


def test_same_when_unfolded():
    report = compare_layered(repeated_mm(), written_out_mm())
    assert report.verdict == "same_when_unfolded"
    assert "other writes out" in report.layers["unfolded"].message
    assert report.layers["aligned"].status == "skipped"


def test_alignable_by_split():
    report = compare_layered(make_mm([1.0, 3.0, 4.0]), make_mm([4.0, 4.0]))
    assert report.verdict == "alignable"
    assert [step.operation for step in report.alignment] == ["split", "match"]
    table = report.measure_table()
    assert table.operation.tolist() == ["split", "match"]
    assert table.preferred_count.tolist() == ["1+2", "3"]


def test_different():
    report = compare_layered(make_mm([4.0, 4.0, 2.0, 4.0]), make_mm([4.0, 4.0, 4.0]))
    assert report.verdict == "different"
    assert report.summary()["n_insert"] == 1
    assert "has no counterpart in other" in report.to_text()


SUMMARY_OF_IDENTICAL_MAPS = dict(
    preferred="preferred",
    other="other",
    verdict="identical",
    n_preferred=3,
    n_other=3,
    duration_preferred=8.0,
    duration_other=8.0,
    lengths_compared=True,
    compared_fields="qstamp, number, time_signature, actual_length",
    undefined_fields="name, nominal_length, start_repeat, end_repeat, volta, next",
    differing_fields="",
    number_offset=None,
    n_preferred_unfolded=None,
    n_other_unfolded=None,
    n_change_length=None,
    n_change_time_signature=None,
    n_join=None,
    n_split=None,
    n_insert=None,
    n_delete=None,
    message=(
        "count: 3 vs. 3 measures; total durations 8q vs. 8q | fields: the 4 of 10 fields defined on both sides are "
        "identical; not compared: name, nominal_length, start_repeat, end_repeat, volta, next"
    ),
)


def test_summary_of_identical_maps():
    report = compare_layered(make_mm([1.0, 4.0, 3.0]), make_mm([1.0, 4.0, 3.0]))
    assert report.summary() == SUMMARY_OF_IDENTICAL_MAPS
    assert list(report.summary()) == list(SUMMARY_OF_IDENTICAL_MAPS)


def test_summary_of_same_measures():
    report = compare_layered(
        make_mm([1.0, 4.0, 3.0], numbers=[0, 1, 2]), make_mm([1.0, 4.0, 3.0])
    )
    assert report.summary() == dict(
        SUMMARY_OF_IDENTICAL_MAPS,
        verdict="same_measures",
        differing_fields="number",
        number_offset=1,
        message=(
            "count: 3 vs. 3 measures; total durations 8q vs. 8q | fields: measure numbers offset by +1 in 1–3; "
            "not compared: name, nominal_length, start_repeat, end_repeat, volta, next"
        ),
    )


def test_summary_of_alignable_maps():
    report = compare_layered(make_mm([1.0, 3.0, 4.0]), make_mm([4.0, 4.0]))
    assert report.summary() == dict(
        SUMMARY_OF_IDENTICAL_MAPS,
        verdict="alignable",
        n_other=2,
        compared_fields="",
        undefined_fields="",
        n_change_length=0,
        n_change_time_signature=0,
        n_join=0,
        n_split=1,
        n_insert=0,
        n_delete=0,
        message="count: 3 vs. 2 measures; total durations 8q vs. 8q | aligned: folded sequences: 1× split",
    )


def test_text_of_a_different_report():
    report = compare_layered(
        make_mm([4.0, 4.0, 2.0, 4.0]),
        make_mm([4.0, 4.0, 4.0]),
        preferred_name="a",
        other_name="b",
    )
    assert report.to_text() == "\n".join(
        [
            "a (preferred) vs. b (other): DIFFERENT",
            "  [differs] count: 4 vs. 3 measures; total durations 14q vs. 12q",
            "  [skipped] fields: ",
            "  [skipped] unfolded: ",
            "  [differs] aligned: folded sequences: 1× insert",
            "  Alignment of the folded sequences:",
            "    - preferred 3 (2q) has no counterpart in other",
        ]
    )
    assert str(report) == report.to_text()


def test_align_measure_sequences_join():
    steps = align_measure_sequences([(1, 4.0, None)], [(1, 1.0, None), (2, 3.0, None)])
    assert len(steps) == 1 and steps[0].operation == "join"
    assert steps[0].other == (1, 2)


def test_compare_pairs_writes_outputs(tmp_path):
    summary, reports = compare_pairs(
        [(repeated_mm(), written_out_mm()), (written_out_mm(), written_out_mm())],
        names=[("a", "b"), ("c", "d")],
        output_directory=tmp_path,
    )
    assert summary.verdict.tolist() == ["same_when_unfolded", "identical"]
    assert (tmp_path / "comparison_summary.tsv").is_file()
    assert (tmp_path / "a_vs_b.txt").is_file()
    assert not (tmp_path / "c_vs_d.txt").exists()


# Measure maps without lengths, e.g. from a source that only enumerates measures (detected measure boxes of a scan)


def make_mm_without_lengths(numbers) -> MeasureMap:
    return MeasureMap.from_array(count=range(1, len(numbers) + 1), number=numbers)


def test_count_mismatch_without_lengths(tmp_path):
    """Five measures against four, neither side defines lengths: the surplus measure is the one whose number has no
    counterpart, and the report can be written."""
    preferred = make_mm_without_lengths([1, 2, 3, 4, 5])
    other = make_mm_without_lengths([1, 2, 3, 4])
    report = compare_layered(preferred, other)
    assert report.verdict == "different"
    assert report.layers["count"].details["lengths_compared"] is False
    assert "without measure lengths" in report.layers["count"].message
    edits = [
        (s.operation, s.preferred, s.other)
        for s in report.alignment
        if s.operation != "match"
    ]
    assert edits == [("insert", (5,), ())]
    assert "preferred 5 has no counterpart in other" in report.to_text()
    summary, _ = compare_pairs(
        [(preferred, other)], names=[("a", "b")], output_directory=tmp_path
    )
    assert summary.verdict.tolist() == ["different"]
    assert (tmp_path / "a_vs_b.txt").is_file()
    assert (tmp_path / "a_vs_b.tsv").is_file()


def test_missing_measure_is_located_by_number():
    """All measures have the same length, so only the numbers can tell which one is missing."""
    preferred = make_mm([4.0] * 5, numbers=[1, 2, 3, 4, 5])
    other = make_mm([4.0] * 4, numbers=[1, 2, 4, 5])
    report = compare_layered(preferred, other)
    edits = [
        (s.operation, s.preferred, s.other)
        for s in report.alignment
        if s.operation != "match"
    ]
    assert edits == [("insert", (3,), ())]


def test_lengths_on_one_side_only():
    """A measure with a length is not different from a measure without one."""
    with_lengths = make_mm([1.0, 4.0, 4.0, 3.0], numbers=[0, 1, 2, 3])
    same_count = compare_layered(with_lengths, make_mm_without_lengths([0, 1, 2, 3]))
    assert same_count.verdict == "identical"
    assert "actual_length" in same_count.layers["fields"].details["undefined"]
    one_less = compare_layered(with_lengths, make_mm_without_lengths([0, 1, 2]))
    assert one_less.verdict == "different"
    assert one_less.summary()["n_change_length"] == 0
    assert one_less.summary()["n_insert"] == 1
    assert "preferred 4 (3q) has no counterpart in other" in one_less.to_text()


def test_align_measure_sequences_prefers_equal_numbers():
    preferred = [(1, None, None, 10), (2, None, None, 11), (3, None, None, 12)]
    other = [(1, None, None, 11), (2, None, None, 12)]
    steps = align_measure_sequences(preferred, other)
    assert [(s.operation, s.preferred, s.other) for s in steps] == [
        ("insert", (1,), ()),
        ("match", (2,), (1,)),
        ("match", (3,), (2,)),
    ]


ANACRUSIS_AND_FIVE_MEASURES = [
    (1, 1.0, "4/4", 0),
    (2, 4.0, "4/4", 1),
    (3, 4.0, "4/4", 2),
    (4, 4.0, "4/4", 3),
    (5, 4.0, "4/4", 4),
    (6, 3.0, "4/4", 5),
]
INSERT_OF_PREFERRED_COUNT_5 = [
    ("match", (1,), (1,)),
    ("match", (2,), (2,)),
    ("match", (3,), (3,)),
    ("match", (4,), (4,)),
    ("insert", (5,), ()),
    ("match", (6,), (5,)),
]


def other_without_fifth_measure(numbers):
    lengths = [1.0, 4.0, 4.0, 4.0, 3.0]
    return [
        (count, length, "4/4", number)
        for count, (length, number) in enumerate(zip(lengths, numbers), 1)
    ]


def test_surplus_measure_is_located_by_number_after_an_anacrusis():
    """The other side lacks number 4 and kept its numbering."""
    steps = align_measure_sequences(
        ANACRUSIS_AND_FIVE_MEASURES, other_without_fifth_measure([0, 1, 2, 3, 5])
    )
    assert [
        (s.operation, s.preferred, s.other) for s in steps
    ] == INSERT_OF_PREFERRED_COUNT_5


def test_surplus_measure_is_located_when_numbers_are_offset_throughout():
    """The other side numbers from 1 where the preferred side numbers from 0, and lacks its number 5."""
    steps = align_measure_sequences(
        ANACRUSIS_AND_FIVE_MEASURES, other_without_fifth_measure([1, 2, 3, 4, 6])
    )
    assert [
        (s.operation, s.preferred, s.other) for s in steps
    ] == INSERT_OF_PREFERRED_COUNT_5


def test_position_among_equal_measures_is_arbitrary_when_other_is_renumbered():
    """Neither lengths nor numbers say which measure the other side lost. The result is the one the rule gives; it
    does not claim that the last measure is the missing one."""
    preferred = [(count, 4.0, "4/4", count) for count in range(1, 6)]
    other = [(count, 4.0, "4/4", count) for count in range(1, 5)]
    steps = align_measure_sequences(preferred, other)
    assert [(s.operation, s.preferred, s.other) for s in steps] == [
        ("match", (1,), (1,)),
        ("match", (2,), (2,)),
        ("match", (3,), (3,)),
        ("match", (4,), (4,)),
        ("insert", (5,), ()),
    ]


def test_split_at_the_end_of_a_sequence():
    steps = align_measure_sequences(
        [(1, 4.0, None), (2, 3.0, None), (3, 1.0, None)],
        [(1, 4.0, None), (2, 4.0, None)],
    )
    assert [(s.operation, s.preferred, s.other) for s in steps] == [
        ("match", (1,), (1,)),
        ("split", (2, 3), (2,)),
    ]


@pytest.mark.parametrize("change_cost", [2.0, 1.0])
def test_change_is_kept_when_insert_and_delete_cost_the_same(change_cost):
    """With change_cost=2.0 and gap_cost=1.0, one change costs as much as an insert plus a delete."""
    steps = align_measure_sequences(
        [(1, 4.0, None)], [(1, 3.0, None)], gap_cost=1.0, change_cost=change_cost
    )
    assert [(s.operation, s.preferred, s.other) for s in steps] == [
        ("change_length", (1,), (1,))
    ]


def test_describe_join_and_split():
    split = AlignmentStep(
        operation="split",
        preferred=(11, 12),
        other=(11,),
        preferred_lengths=(3.0, 1.0),
        other_lengths=(4.0,),
    )
    assert split.describe() == (
        "other 11 (4q) would need to be split to correspond to preferred 11+12 (3q+1q)"
    )
    join = AlignmentStep(
        operation="join",
        preferred=(12,),
        other=(12, 10),
        preferred_lengths=(4.0,),
        other_lengths=(3.0, 1.0),
    )
    assert join.describe() == (
        "other 12+10 (3q+1q) would need to be joined to correspond to preferred 12 (4q)"
    )
    without_lengths = AlignmentStep(operation="join", preferred=(1,), other=(1, 2))
    assert without_lengths.describe() == (
        "other 1+2 would need to be joined to correspond to preferred 1"
    )
    computed = align_measure_sequences(
        [(1, 4.0, None)], [(1, 1.0, None), (2, 3.0, None)]
    )
    assert [step.describe() for step in computed] == [
        "other 1+2 (1q+3q) would need to be joined to correspond to preferred 1 (4q)"
    ]


# Unfolding from repeat signs and endings


def test_unfold_second_ending_of_two_measures():
    """|: 1 [1. 2 3 :| [2. 4 5 | 6"""
    mm = make_mm(
        [4.0] * 6,
        start_repeat=[True] + [False] * 5,
        end_repeat=[False, False, True, False, False, False],
        volta=[None, 1, 1, 2, 2, None],
    )
    assert unfold(mm) == [1, 2, 3, 1, 4, 5, 6]


def test_unfold_three_endings():
    """|: 1 [1. 2 :| [2. 3 :| [3. 4 | 5"""
    mm = make_mm(
        [4.0] * 5,
        start_repeat=[True] + [False] * 4,
        end_repeat=[False, True, True, False, False],
        volta=[None, 1, 2, 3, None],
    )
    assert unfold(mm) == [1, 2, 1, 3, 1, 4, 5]


def test_unfold_two_repeated_sections_with_endings():
    """|: 1 [1. 2 :| [2. 3 |: 4 [1. 5 :| [2. 6 | 7"""
    mm = make_mm(
        [4.0] * 7,
        start_repeat=[True, False, False, True, False, False, False],
        end_repeat=[False, True, False, False, True, False, False],
        volta=[None, 1, 2, None, 1, 2, None],
    )
    assert unfold(mm) == [1, 2, 1, 3, 4, 5, 4, 6, 7]


def test_unfold_end_repeat_without_start_repeat():
    """1 2 :| 3 4 :| repeats from the beginning and then from the previous end repeat."""
    mm = make_mm([4.0] * 4, end_repeat=[False, True, False, True])
    assert unfold(mm) == [1, 2, 1, 2, 3, 4, 3, 4]


def test_unfold_endings_without_end_repeat_warn(caplog):
    mm = make_mm([4.0] * 4, volta=[None, 1, 2, None])
    with caplog.at_level("WARNING"):
        assert unfold(mm) == [1, 2, 4]
    assert "do not include an end repeat" in caplog.text


def test_unfold_next_with_ids_unknown_targets_and_loops(caplog):
    with_ids = MeasureMap.from_dicts(
        [
            dict(ID="a", count=1, next=["b"]),
            dict(ID="b", count=2, next=["a", "c"]),
            dict(ID="c", count=3, next=[]),
        ]
    )
    assert unfold(with_ids) == [1, 2, 1, 2, 3]
    with caplog.at_level("WARNING"):
        assert unfold(make_mm([4.0] * 4, next=[[2], [99], [4], [-1]])) == [1, 2]
    assert "neither a count nor an ID" in caplog.text
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert unfold(make_mm([4.0] * 2, next=[[2], [1]])) == [1, 2] * 10
    assert "endless loop" in caplog.text


def test_unfold_adjacent_repeated_sections():
    """|: 1 2 :||: 3 4 :| 5"""
    mm = make_mm(
        [4.0] * 5,
        start_repeat=[True, False, True, False, False],
        end_repeat=[False, True, False, True, False],
    )
    assert unfold(mm) == [1, 2, 1, 2, 3, 4, 3, 4, 5]


def test_unfold_nested_repeats_are_not_supported():
    """|: 1 |: 2 :| 3 :| would be played 1 2 2 3 1 2 2 3. The inference from repeat signs follows one repeated
    section at a time and yields something else, which this test pins."""
    mm = make_mm(
        [4.0] * 3,
        start_repeat=[True, True, False],
        end_repeat=[False, True, True],
    )
    assert unfold(mm) == [1, 2, 2, 3, 3]


IGNORED_SIGNS_WARNING = (
    "Some measures specify 'next', so the play-through follows 'next' only: the repeat signs and voltas of the "
    "measures without 'next' are ignored (counts 1, 2)."
)


def test_unfold_next_on_some_measures_ignores_repeat_signs(caplog):
    mm = MeasureMap.from_dicts(
        [
            dict(count=1, start_repeat=True),
            dict(count=2, end_repeat=True),
            dict(count=3, next=[-1]),
        ]
    )
    with caplog.at_level("WARNING"):
        assert unfold(mm) == [1, 2, 3]
    assert [record.getMessage() for record in caplog.records] == [IGNORED_SIGNS_WARNING]


def test_unfold_next_on_every_measure_does_not_warn(caplog):
    mm = make_mm(
        [4.0] * 4,
        start_repeat=[True, False, False, False],
        end_repeat=[False, True, False, False],
        volta=[None, 1, 2, None],
        next=[[2, 3], [1], [4], [-1]],
    )
    with caplog.at_level("WARNING"):
        assert unfold(mm) == [1, 2, 1, 3, 4]
    assert caplog.records == []


def test_unfold_next_without_other_signs_does_not_warn(caplog):
    mm = MeasureMap.from_dicts([dict(count=1), dict(count=2), dict(count=3, next=[-1])])
    with caplog.at_level("WARNING"):
        assert unfold(mm) == [1, 2, 3]
    assert caplog.records == []


# What a verdict rests on


def test_same_count_when_no_field_is_defined_on_both_sides():
    with_fields = make_mm([1.0, 4.0, 3.0], numbers=[0, 1, 2])
    counts_only = MeasureMap.from_array(count=[1, 2, 3])
    report = compare_layered(with_fields, counts_only)
    assert report.verdict == "same_count"
    assert report.layers["fields"].message == "no field is defined on both sides"
    summary = report.summary()
    assert summary["compared_fields"] == ""
    assert summary["lengths_compared"] is False


def test_summary_lists_what_was_compared():
    report = compare_layered(
        make_mm([1.0, 4.0, 3.0]), make_mm_without_lengths([1, 2, 3])
    )
    assert report.verdict == "identical"
    summary = report.summary()
    assert summary["compared_fields"] == "number"
    assert (
        summary["undefined_fields"]
        == "qstamp, name, time_signature, nominal_length, actual_length, start_repeat, end_repeat, volta, next"
    )
    assert summary["lengths_compared"] is False
    assert report.layers["fields"].message == (
        "the 1 of 10 fields defined on both sides are identical; not compared: qstamp, name, time_signature, "
        "nominal_length, actual_length, start_repeat, end_repeat, volta, next"
    )


def test_unfolded_without_lengths_says_what_it_rests_on():
    report = compare_layered(repeated_mm(), MeasureMap.from_array(count=range(1, 7)))
    assert report.verdict == "same_when_unfolded"
    assert "rests on the numbers of measures alone" in report.layers["unfolded"].message


def test_fields_argument():
    """The structural fields decide about the verdict even if they are not among the requested fields."""
    report = compare_layered(
        make_mm([4.0, 4.0]), make_mm([4.0, 2.0]), fields=["number"]
    )
    assert report.verdict == "same_count_different_measures"
    with pytest.raises(ValueError, match="Unknown field"):
        compare_layered(make_mm([4.0, 4.0]), make_mm([4.0, 4.0]), fields=["duration"])


def test_no_unfolding_without_repeats():
    report = compare_layered(make_mm([4.0, 4.0]), make_mm([2.0, 2.0, 4.0]))
    assert report.layers["unfolded"].status == "skipped"
    assert report.alignment_basis == "folded"
    assert report.verdict == "alignable"


def test_change_of_time_signature_is_not_a_change_of_length():
    preferred = MeasureMap.from_array(
        count=[1, 2], actual_length=[4.0, 4.0], time_signature=["4/4"] * 2
    )
    other = MeasureMap.from_array(
        count=[1, 2], actual_length=[4.0, 4.0], time_signature=["2/2"] * 2
    )
    report = compare_layered(preferred, other)
    assert report.verdict == "same_count_different_measures"
    assert [s.operation for s in report.alignment] == ["change_time_signature"] * 2
    assert report.alignment[0].describe() == (
        "preferred 1 (4/4) ≠ other 1 (2/2): different time signature"
    )
    assert report.summary()["n_change_time_signature"] == 2
    assert report.summary()["n_change_length"] == 0


def test_alignment_with_joins_and_splits_only_is_preferred():
    """Folded, the two can be aligned by a split and a join; unfolded, the alignment needs a change of length.
    'alignable' is defined as 'can be aligned with joins and splits only', so the folded alignment counts.
    """
    preferred = MeasureMap.from_array(
        count=[1, 2, 3],
        actual_length=[1.0, 2.0, 3.0],
        start_repeat=[False, True, False],
        end_repeat=[False, True, False],
    )
    other = MeasureMap.from_array(
        count=[1, 2, 3],
        actual_length=[3.0, 2.0, 1.0],
        start_repeat=[False] * 3,
        end_repeat=[False] * 3,
    )
    report = compare_layered(preferred, other)
    assert report.verdict == "alignable"
    assert report.alignment_basis == "folded"
    assert [(s.operation, s.preferred, s.other) for s in report.alignment] == [
        ("split", (1, 2), (1,)),
        ("join", (3,), (2, 3)),
    ]
    assert report.layers["aligned"].details["n_edits"] == {"folded": 2, "unfolded": 2}


def test_align_measure_sequences_delete():
    steps = align_measure_sequences(
        [(1, 4.0, None), (2, 3.0, None)],
        [(1, 4.0, None), (2, 2.0, None), (3, 3.0, None)],
    )
    assert [(s.operation, s.preferred, s.other) for s in steps] == [
        ("match", (1,), (1,)),
        ("delete", (), (2,)),
        ("match", (2,), (3,)),
    ]


# The measure table


def test_measure_table_for_equal_counts():
    report = compare_layered(
        make_mm([1.0, 4.0, 3.0], numbers=[0, 1, 2]), make_mm([1.0, 4.0, 3.0])
    )
    table = report.measure_table()
    assert table.operation.tolist() == ["match"] * 3
    assert table.differing.tolist() == ["number"] * 3
    assert table.preferred_count.tolist() == ["1", "2", "3"]
    assert table.preferred_number.tolist() == [0, 1, 2]
    assert table.other_number.tolist() == [1, 2, 3]
    assert table.columns.tolist()[:4] == [
        "operation",
        "differing",
        "preferred_count",
        "other_count",
    ]


def test_measure_table_follows_the_play_throughs():
    table = compare_layered(repeated_mm(), written_out_mm()).measure_table()
    assert table.preferred_count.tolist() == ["1", "2", "1", "2", "3", "4"]
    assert table.other_count.tolist() == ["1", "2", "3", "4", "5", "6"]


def test_measure_table_joins_values_of_split_measures():
    table = compare_layered(
        make_mm([1.0, 3.0, 4.0]), make_mm([4.0, 4.0])
    ).measure_table()
    assert table.preferred_actual_length.tolist() == ["1.0+3.0", 4.0]
    assert table.other_actual_length.tolist() == [4.0, 4.0]


# Batches


def test_compare_pairs_keeps_equally_named_files_apart(tmp_path):
    """Two folders with equally named files: the names in the summary and the report files must not collide."""
    for folder, lengths in (("A", [4.0, 2.0]), ("B", [4.0, 3.0])):
        (tmp_path / folder).mkdir()
        make_mm([4.0, 4.0]).to_json_file(tmp_path / folder / "preferred.mm.json")
        make_mm(lengths).to_json_file(tmp_path / folder / "other.mm.json")
    pairs = [
        (tmp_path / folder / "preferred.mm.json", tmp_path / folder / "other.mm.json")
        for folder in ("A", "B")
    ]
    out = tmp_path / "out"
    summary, _ = compare_pairs(pairs, output_directory=out)
    assert summary.preferred.tolist() == ["A/preferred.mm.json", "B/preferred.mm.json"]
    assert summary.other.tolist() == ["A/other.mm.json", "B/other.mm.json"]
    assert sorted(path.name for path in out.iterdir()) == [
        "A_preferred_vs_A_other.tsv",
        "A_preferred_vs_A_other.txt",
        "B_preferred_vs_B_other.tsv",
        "B_preferred_vs_B_other.txt",
        "comparison_summary.tsv",
    ]


def test_compare_pairs_numbers_colliding_report_files(tmp_path):
    a, b = make_mm([4.0, 4.0]), make_mm([4.0, 2.0])
    compare_pairs(
        [(a, b), (b, a)], names=[("x", "y"), ("x", "y")], output_directory=tmp_path
    )
    assert (tmp_path / "x_vs_y.txt").is_file()
    assert (tmp_path / "x_vs_y_2.txt").is_file()
    assert "4q" in (tmp_path / "x_vs_y.txt").read_text(encoding="utf-8")


def test_compare_pairs_names_and_errors(tmp_path, caplog):
    a = make_mm([4.0, 4.0])
    with pytest.raises(ValueError, match="1 names for 2 pairs"):
        compare_pairs([(a, a), (a, a)], names=[("a", "b")])
    missing = tmp_path / "missing.mm.json"
    with caplog.at_level("DEBUG", logger="pymeasuremap.compare"):
        summary, reports = compare_pairs([(a, a), (missing, a)])
    assert summary.preferred.tolist() == ["preferred_1", "missing.mm.json"]
    assert summary.verdict.tolist() == ["identical", "error"]
    assert reports[1] is None
    message = (
        f"FileNotFoundError: [Errno 2] No such file or directory: {str(missing)!r}"
    )
    assert summary.message[1] == message
    assert [
        (record.levelname, record.getMessage(), record.exc_info is not None)
        for record in caplog.records
        if record.name == "pymeasuremap.compare"
    ] == [
        (
            "WARNING",
            f"Comparing missing.mm.json with other_2 failed: {message}",
            False,
        ),
        (
            "DEBUG",
            "Traceback of the failed comparison of missing.mm.json with other_2:",
            True,
        ),
    ]


def test_compare_pairs_continues_when_a_report_cannot_be_written(tmp_path):
    a, b, c = make_mm([4.0, 4.0]), make_mm([4.0, 2.0]), make_mm([4.0, 3.0])
    blocked = tmp_path / "x_vs_y.tsv"
    blocked.mkdir()
    with pytest.raises(OSError) as error:
        open(blocked, "w")
    expected_error = repr(error.value)
    summary, reports = compare_pairs(
        [(a, b), (a, c)], names=[("x", "y"), ("p", "q")], output_directory=tmp_path
    )
    assert summary.verdict.tolist() == ["same_count_different_measures"] * 2
    assert summary.output_error.isna().tolist() == [False, True]
    assert summary.output_error[0] == expected_error
    assert [report.verdict for report in reports] == [
        "same_count_different_measures"
    ] * 2
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "comparison_summary.tsv",
        "p_vs_q.tsv",
        "p_vs_q.txt",
        "x_vs_y.tsv",
    ]
    assert blocked.is_dir()
    with open(tmp_path / "comparison_summary.tsv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    assert [(row["preferred"], row["other"], row["output_error"]) for row in rows] == [
        ("x", "y", expected_error),
        ("p", "q", ""),
    ]
