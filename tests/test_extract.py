from music21 import corpus

from pymeasuremap.extract import m21_stream_to_measure_map


def test_m21_extraction():
    score = corpus.parse("bach/bwv66.6")  # four parts, starting with an anacrusis
    mm = m21_stream_to_measure_map(score)
    assert len(mm) == 10
    assert (mm[1].number, mm[1].actual_length) == (0, 1.0)
    assert mm[2].qstamp == 1.0
