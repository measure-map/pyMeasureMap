from pymeasuremap.base import MeasureMap
from pymeasuremap.compare import (
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
