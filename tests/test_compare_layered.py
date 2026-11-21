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
