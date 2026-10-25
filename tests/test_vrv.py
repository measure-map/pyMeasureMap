import logging
from pathlib import Path

import pytest
from test_repeats import MEI_TEMPLATE, measure

pytest.importorskip("verovio")

from pymeasuremap.vrv import verovio_to_measure_map  # noqa: E402

DATA = Path(__file__).parent / "data"


def mei_with_voltas():
    body = "".join(
        [
            measure(1),
            measure(2, 'left="rptstart"'),
            '<ending xml:id="e1" n="1">',
            measure(3, 'right="rptend"'),
            "</ending>",
            '<ending xml:id="e2" n="2">',
            measure(4),
            "</ending>",
        ]
    )
    return MEI_TEMPLATE.format(body)


def test_mei_string():
    mm = verovio_to_measure_map(mei_with_voltas())
    assert [m.ID for m in mm] == ["m1", "m2", "m3", "m4"]
    assert [m.qstamp for m in mm] == [0.0, 3.0, 6.0, 9.0]
    assert [m.actual_length for m in mm] == [3.0] * 4
    assert [m.name for m in mm] == ["1", "2", "3a", "4b"]
    assert [m.next for m in mm] == [[2], [3, 4], [2], [-1]]


def test_next_as_ids():
    mm = verovio_to_measure_map(mei_with_voltas(), next_as="ID")
    assert [m.next for m in mm] == [["m2"], ["m3", "m4"], ["m2"], []]


def test_musicxml_matches_expansion(caplog):
    with caplog.at_level(logging.WARNING, logger="pymeasuremap.vrv"):
        mm = verovio_to_measure_map(DATA / "voltas_meter_change.musicxml")
    assert "disagrees" not in caplog.text
    assert all(m.ID for m in mm)
    assert [m.number for m in mm] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert [m.time_signature for m in mm] == ["3/4"] * 5 + ["2/4"] * 3
    assert [m.actual_length for m in mm] == [1.0, 3.0, 3.0, 3.0, 3.0, 2.0, 2.0, 1.0]
    assert [m.next for m in mm] == [[2], [3], [4, 5], [2], [6], [7], [6, 8], [-1]]
    from_expansion = verovio_to_measure_map(
        DATA / "voltas_meter_change.musicxml", next_from="expansion"
    )
    assert [m.next for m in from_expansion] == [m.next for m in mm]
