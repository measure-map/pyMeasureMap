from music21 import corpus, note, stream

from pymeasuremap.extract import m21_stream_to_measure_map


def test_m21_extraction():
    score = corpus.parse("bach/bwv66.6")  # four parts, starting with an anacrusis
    mm = m21_stream_to_measure_map(score)
    assert len(mm) == 10
    assert (mm[1].number, mm[1].actual_length) == (0, 1.0)
    assert mm[2].qstamp == 1.0


def test_m21_extraction_without_time_signature():
    part = stream.Part()
    for _ in range(3):
        measure = stream.Measure()
        measure.append(note.Note(quarterLength=2))
        part.append(measure)
    mm = m21_stream_to_measure_map(part)
    assert (mm[1].time_signature, mm[1].nominal_length) == (None, None)
    assert (mm[3].qstamp, mm[3].actual_length) == (4.0, 2.0)
