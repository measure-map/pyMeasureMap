"""Read the measure structure of MEI documents.

Only the Python standard library is needed. The parser walks the notated (unexpanded) score in document order and
collects, for every ``<measure>``, its ID, number, barlines, volta membership, jump markers, and the current meter.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple

from pymeasuremap.repeats import MeasureStructure

module_logger = logging.getLogger(__name__)

MEI_NS = "{http://www.music-encoding.org/ns/mei}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
METER_SYMBOLS = {"common": "4/4", "cut": "2/2"}


@dataclass(kw_only=True)
class MeiMeasure(MeasureStructure):
    """A measure as read from MEI."""

    n: Optional[str] = None
    """The value of ``measure/@n``."""
    left: Optional[str] = None
    right: Optional[str] = None
    metcon: Optional[bool] = None
    ending_label: Optional[str] = None
    time_signature: Optional[str] = None
    """The meter in effect, as '<count>/<unit>'."""
    has_expansion: bool = False


def ending_numbers(ending: ET.Element) -> Tuple[int, ...]:
    """The passes for which an ``<ending>`` is played.

    MuseScore's exporter records them as ``@type="mscore-ending-1 mscore-ending-2"``, which takes precedence over
    numbers parsed from ``@n`` or ``@label`` (e.g. '1.', '1, 2', '1-3').
    """
    numbers = [
        int(x) for x in re.findall(r"mscore-ending-(\d+)", ending.get("type", ""))
    ]
    if numbers:
        return tuple(numbers)
    for attribute in ("n", "label"):
        value = ending.get(attribute)
        if not value:
            continue
        for start, stop in re.findall(r"(\d+)\s*(?:[-–]\s*(\d+))?", value):
            numbers.extend(range(int(start), int(stop or start) + 1))
        if numbers:
            return tuple(numbers)
    return ()


def repeat_mark_kind(repeat_mark: ET.Element) -> Optional[str]:
    """Maps a ``<repeatMark>`` to one of :data:`pymeasuremap.repeats.JUMP_KINDS`."""
    func = repeat_mark.get("func")
    mark_type = repeat_mark.get("type", "")
    text = "".join(repeat_mark.itertext()).strip().lower()
    if func == "coda" and "to-coda" in mark_type:
        return "tocoda"
    if func == "daCapo" and text:
        # MuseScore's exporter writes every jump as daCapo; trust the text if it unambiguously says D.S.
        says_ds = re.search(r"\bd\.?\s*s\.|dal\s+segno", text)
        says_dc = re.search(r"\bd\.?\s*c\.|da\s*capo", text)
        if says_ds and not says_dc:
            return "dalSegno"
    return func


def meter_from(element: ET.Element) -> Optional[str]:
    """Reads the meter from a ``<scoreDef>``, ``<staffDef>`` or ``<meterSig>``."""
    if element.tag == f"{MEI_NS}meterSig":
        count, unit, sym = element.get("count"), element.get("unit"), element.get("sym")
    else:
        count, unit, sym = (
            element.get("meter.count"),
            element.get("meter.unit"),
            element.get("meter.sym"),
        )
        meter_sig = element.find(f"{MEI_NS}meterSig")
        if count is None and sym is None and meter_sig is not None:
            return meter_from(meter_sig)
    if count and unit:
        return f"{count}/{unit}"
    if sym in METER_SYMBOLS:
        return METER_SYMBOLS[sym]
    return None


def parse_mei_measures(mei: str | bytes | ET.Element) -> List[MeiMeasure]:
    """Returns the measures of an MEI document in score order.

    Malformed exports are tolerated: measures nested inside measures or placed directly inside ``<mdiv>`` are
    included in document order.
    """
    root = mei if isinstance(mei, ET.Element) else ET.fromstring(mei)
    has_expansion = root.find(f".//{MEI_NS}expansion") is not None
    measures: List[MeiMeasure] = []
    meter = None

    def walk(element: ET.Element, ending: Optional[ET.Element] = None):
        nonlocal meter
        for child in element:
            tag = child.tag.removeprefix(MEI_NS)
            if tag == "scoreDef":
                # the score-wide meter or, failing that, the first staff's (staves may change meter individually)
                new_meter = meter_from(child) or next(
                    filter(None, map(meter_from, child.iter(f"{MEI_NS}staffDef"))), None
                )
                if new_meter:
                    meter = new_meter
                walk(child, ending)
            elif tag == "ending":
                walk(child, child)
            elif tag == "measure":
                read_measure(child, ending)
            elif tag != "expansion":
                walk(child, ending)

    def read_measure(element: ET.Element, ending: Optional[ET.Element]):
        nonlocal meter
        right = element.get("right")
        play_count = 2
        if match := re.search(r"mscore-repeat-(\d+)", element.get("type", "")):
            # ms3 (and the notation) treat a playCount of 1 as a repeat, too
            play_count = max(2, int(match.group(1)))
        metcon = element.get("metcon")
        measure = MeiMeasure(
            ID=element.get(XML_ID),
            n=element.get("n"),
            left=element.get("left"),
            right=right,
            metcon=None if metcon is None else metcon == "true",
            start_repeat=element.get("left") in ("rptstart", "rptboth"),
            end_repeat=right in ("rptend", "rptboth"),
            play_count=play_count,
            has_expansion=has_expansion,
        )
        if ending is not None:
            measure.ending = ending.get(XML_ID) or str(id(ending))
            measure.ending_numbers = ending_numbers(ending)
            measure.ending_label = ending.get("label") or ending.get("n")
        measures.append(measure)
        jumps, nested = set(), []
        stack = list(element)
        while stack:  # the measure's content, stopping at (malformed) nested measures
            descendant = stack.pop(0)
            tag = descendant.tag.removeprefix(MEI_NS)
            if tag == "measure":
                nested.append(descendant)
                continue
            if tag == "repeatMark":
                if kind := repeat_mark_kind(descendant):
                    jumps.add(kind)
            elif tag == "meterSig" and (new_meter := meter_from(descendant)):
                meter = new_meter
            stack[:0] = list(descendant)
        measure.jumps = frozenset(jumps)
        measure.time_signature = meter
        if nested:
            module_logger.warning(
                f"Measure {measure.ID!r} contains {len(nested)} nested <measure> elements."
            )
            for nested_measure in nested:
                read_measure(nested_measure, ending)

    for mdiv in root.iter(f"{MEI_NS}mdiv"):
        if (
            mdiv.find(f"{MEI_NS}mdiv") is None
        ):  # innermost; malformed exports place measures directly in <mdiv>
            walk(mdiv)
    return measures
