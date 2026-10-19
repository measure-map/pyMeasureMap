from music21 import corpus, note, spanner, stream

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


def test_m21_extraction_of_voltas():
    score = corpus.parse("joplin/maple_leaf_rag")
    mm = m21_stream_to_measure_map(score)
    assert [(mm[count].number, mm[count].volta) for count in (33, 34, 35, 36)] == [
        (32, None),
        (33, 1),
        (34, 2),
        (35, None),
    ]


def test_m21_extraction_of_multi_number_volta():
    part = stream.Part()
    for _ in range(3):
        measure = stream.Measure()
        measure.append(note.Note(quarterLength=4))
        part.append(measure)
    first, second, third = part.getElementsByClass(stream.Measure)
    part.insert(0, spanner.RepeatBracket(second, number="1, 2"))
    part.insert(0, spanner.RepeatBracket(third, number=3))
    mm = m21_stream_to_measure_map(part)
    assert [measure.volta for measure in mm] == [None, 1, 3]
