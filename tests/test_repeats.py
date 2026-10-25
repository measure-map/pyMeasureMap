from pymeasuremap.mei import parse_mei_measures
from pymeasuremap.repeats import END, MeasureStructure, infer_next, perform


def make(*specs):
    """Each spec is a string of flags: '|:' start repeat, ':|' end repeat, 'e1', 'e1,2'... ending (a suffix like
    '#b' distinguishes endings with the same numbers), plus jump kinds."""
    measures = []
    for i, spec in enumerate(specs):
        flags = spec.split()
        ending = next((f for f in flags if f.startswith("e")), None)
        measures.append(
            MeasureStructure(
                ID=str(i + 1),
                start_repeat="|:" in flags,
                end_repeat=":|" in flags,
                ending=ending,
                ending_numbers=(
                    tuple(int(x) for x in ending[1:].split("#")[0].split(","))
                    if ending
                    else ()
                ),
                jumps=frozenset(
                    f
                    for f in flags
                    if f in ("daCapo", "dalSegno", "fine", "segno", "coda", "tocoda")
                ),
            )
        )
    return measures


def counts(sequence):
    return [-1 if i is END else i + 1 for i in sequence]


def test_repeat_with_voltas():
    ms = make("", "|:", "", "e1 :|", "e2", "")
    assert counts(perform(ms)) == [1, 2, 3, 4, 2, 3, 5, 6, -1]


def test_end_repeat_without_start_returns_after_previous_end_repeat():
    ms = make("", ":|", "", ":|", "")
    assert counts(perform(ms)) == [1, 2, 1, 2, 3, 4, 3, 4, 5, -1]


def test_volta_block_keeps_repeat_start():
    # second volta block repeats back to the same start repeat as the first one (ms3/MuseScore behaviour)
    ms = make("|:", "", "e1 :|", "e2", "", "e1 :|", "e2")
    assert counts(perform(ms)) == [1, 2, 3, 1, 2, 4, 5, 6, 1, 2, 4, 5, 7, -1]


def test_three_passes_through_volta_block():
    ms = make("|:", "e1,2", "e1,2 :|", "e3")
    ms[2].play_count = 3
    assert counts(perform(ms)) == [1, 2, 3, 1, 2, 3, 1, 4, -1]


def test_unmatched_volta_continues_without_skipping():
    ms = make("|:", "e1 :|", "e1#b", "")  # second ending mislabelled as '1'
    assert counts(perform(ms)) == [1, 2, 1, 2, 3, 4, -1]


def test_da_capo_al_fine():
    ms = make("", "fine", "", "daCapo")
    assert counts(perform(ms)) == [1, 2, 3, 4, 1, 2, -1]


def test_dal_segno_skips_repeats_and_takes_ending_with_fine():
    ms = make("", "segno |:", "e1 :|", "e2 fine", "dalSegno")
    assert counts(perform(ms)) == [1, 2, 3, 2, 4, 5, 2, 4, -1]


def test_jump_in_volta_takes_precedence_over_repeat():
    ms = make("segno", "|:", "e1 :|", "e2 :| dalSegno", "e3 fine")
    assert counts(perform(ms)) == [1, 2, 3, 2, 4, 1, 2, 5, -1]


def test_to_coda():
    ms = make("", "tocoda", "", "daCapo", "coda", "")
    assert counts(perform(ms)) == [1, 2, 3, 4, 1, 2, 5, 6, -1]


def test_rondeau():
    ms = make("", "fine", "segno", "daCapo", "segno", "daCapo")
    assert counts(perform(ms)) == [1, 2, 3, 4, 1, 2, -1, 5, 6, 1, 2, -1]
    assert [[-1 if x is END else x + 1 for x in s] for s in infer_next(ms)] == [
        [2],
        [3, -1, 5],
        [4],
        [1],
        [6],
        [1],
    ]


MEI_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1">
<music><body><mdiv><score>
<scoreDef meter.count="3" meter.unit="4"><staffGrp><staffDef n="1" lines="5"/></staffGrp></scoreDef>
<section>{}</section>
</score></mdiv></body></music></mei>"""


def measure(i, attrs="", content=""):
    return (
        f'<measure xml:id="m{i}" n="{i}" {attrs}><staff n="1"><layer n="1">'
        f"<mRest/></layer></staff>{content}</measure>"
    )


def test_parse_mei_measures():
    body = "".join(
        [
            measure(1),
            measure(2, 'left="rptstart"'),
            '<ending xml:id="e1" label="1." type="mscore-ending-1 mscore-ending-2">',
            measure(3, 'right="rptend" type="mscore-repeat-3"'),
            "</ending>",
            '<ending xml:id="e2" n="3">',
            measure(4),
            "</ending>",
            '<scoreDef><staffGrp><staffDef n="1" meter.count="2" meter.unit="4"/></staffGrp></scoreDef>',
            measure(
                5,
                content='<repeatMark func="daCapo" tstamp="1">D.S. al Fine</repeatMark>',
            ),
        ]
    )
    ms = parse_mei_measures(MEI_TEMPLATE.format(body))
    assert [m.ID for m in ms] == ["m1", "m2", "m3", "m4", "m5"]
    assert ms[1].start_repeat and ms[2].end_repeat and ms[2].play_count == 3
    assert ms[2].ending_numbers == (1, 2) and ms[3].ending_numbers == (3,)
    assert [m.time_signature for m in ms] == ["3/4"] * 4 + ["2/4"]
    assert ms[4].jumps == {"dalSegno"}  # the text overrides MuseScore's generic daCapo


def test_parse_nested_measures():
    body = measure(1) + measure(2, content=measure(3))
    assert [m.ID for m in parse_mei_measures(MEI_TEMPLATE.format(body))] == [
        "m1",
        "m2",
        "m3",
    ]
