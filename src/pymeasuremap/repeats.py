"""Infer the 'next' field of a MeasureMap from the notated repeat structure.

The functions in this module are format-agnostic: they operate on a sequence of :class:`MeasureStructure` objects
that describe, for each measure in score order, its repeat barlines, the volta (ending) it belongs to, and the
jump markers (segno, coda, D.C., D.S., Fine) it carries. :func:`perform` simulates one play-through of the score and
:func:`infer_next` turns the resulting sequence into successor lists.

The rules follow the behaviour of MuseScore playback (as encoded in the 'next' column of ms3 measures tables):

- An end repeat jumps back to the last start repeat or, if there is none, to the measure following the previous end
  repeat outside a volta (or to the beginning of the piece).
- A measure with an end repeat is repeated ``play_count - 1`` times. Within a volta, the passes are counted for the
  volta block as a whole and the pass number decides which ending is played. If no ending matches the pass number,
  the music continues without skipping.
- A jump (D.C., D.S.) is taken the first time the measure is reached, after its own repeat has been exhausted; within a
  volta, a jump takes precedence over the end repeat. After a jump, repeats are not played again and a volta block is
  entered at the ending containing the Fine or, if there is none, at its last ending.
- After a jump, a Fine ends the piece. If there is a segno after the measure that issued the jump (rondeau pattern),
  the piece may end at the Fine or continue at that segno.
- A 'To Coda' marker, after a jump, skips to the next coda.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

module_logger = logging.getLogger(__name__)

END = None
"""Element of a performed sequence marking that the piece (may) end here."""

JUMP_KINDS = ("daCapo", "dalSegno", "fine", "segno", "coda", "tocoda")


@dataclass(kw_only=True)
class MeasureStructure:
    """The repeat-relevant properties of a single measure."""

    ID: Optional[str] = None
    start_repeat: bool = False
    """Whether the measure begins with a start repeat."""
    end_repeat: bool = False
    """Whether the measure ends with an end repeat."""
    play_count: int = 2
    """How many times the repeated section is played in total."""
    ending: Optional[str] = None
    """Identifier of the volta (ending) the measure belongs to, if any."""
    ending_numbers: Tuple[int, ...] = ()
    """The passes for which this ending is played."""
    jumps: FrozenSet[str] = field(default_factory=frozenset)
    """Any of :data:`JUMP_KINDS`."""


def ending_blocks(
    measures: Sequence[MeasureStructure],
) -> List[List[Tuple[Tuple[int, ...], int, int]]]:
    """Groups the endings into blocks of directly adjacent endings.

    Returns:
        A list of blocks, each a list of ``(ending_numbers, first_index, last_index)`` tuples.
    """
    endings = []
    for i, m in enumerate(measures):
        if m.ending is None:
            continue
        if endings and endings[-1][0] == m.ending and endings[-1][3] == i - 1:
            endings[-1][3] = i
        else:
            endings.append([m.ending, m.ending_numbers, i, i])
    blocks = []
    for _, numbers, first, last in endings:
        if blocks and blocks[-1][-1][2] == first - 1:
            blocks[-1].append((numbers, first, last))
        else:
            blocks.append([(numbers, first, last)])
    return blocks


def perform(
    measures: Sequence[MeasureStructure], max_length: int = 100_000
) -> List[Optional[int]]:
    """Simulates one play-through of the score.

    Returns:
        The sequence of measure indices (0-based) in the order in which they are played. :data:`END` marks the end of
        the piece and, when followed by more indices, a position where the piece may end (e.g. the Fine of a rondeau).
    """
    N = len(measures)
    jumps = [m.jumps for m in measures]
    segnos = [i for i, j in enumerate(jumps) if "segno" in j]
    codas = [i for i, j in enumerate(jumps) if "coda" in j]
    blocks = {block[0][1]: block for block in ending_blocks(measures)}
    block_of: Dict[int, list] = {}
    for block in blocks.values():
        for _, first, last in block:
            for j in range(first, last + 1):
                block_of[j] = block
    jumps_back: Dict[int, int] = {}

    def block_passes(block) -> int:
        return sum(
            jumps_back.get(j, 0)
            for _, first, last in block
            for j in range(first, last + 1)
        )

    def has_fine(ending) -> bool:
        return any("fine" in jumps[j] for j in range(ending[1], ending[2] + 1))

    sequence: List[Optional[int]] = []
    i, repeat_start = 0, 0
    after_jump = False
    jump_origin = None
    jumped = set()
    while i < N:
        if len(sequence) >= max_length:
            module_logger.warning(
                f"Stopped the play-through after {max_length} measures."
            )
            break
        m = measures[i]
        if i in blocks:
            block = blocks[i]
            if after_jump:
                ending = next(
                    (e for e in block if has_fine(e)),
                    max(block, key=lambda e: max(e[0], default=0)),
                )
            else:
                wanted = 1 + block_passes(block)
                ending = next((e for e in block if wanted in e[0]), None)
                if ending is None:
                    module_logger.debug(
                        f"No ending for pass {wanted} at measure index {i}, continuing without skipping."
                    )
            if ending is not None and ending[1] != i:
                i = ending[1]
                continue
        if m.start_repeat and not (
            sequence and sequence[-1] is not END and sequence[-1] >= i
        ):
            repeat_start = i
        sequence.append(i)
        here = jumps[i]
        if after_jump and "fine" in here:
            later = [s for s in segnos if jump_origin is not None and s > jump_origin]
            if not later:
                break
            sequence.append(END)
            i = repeat_start = later[0]
            after_jump = False
            continue
        if after_jump and "tocoda" in here:
            later = [c for c in codas if c > i]
            if later:
                i = later[0]
                continue
        jump = ("daCapo" in here or ("dalSegno" in here and segnos)) and i not in jumped
        if m.end_repeat and not after_jump and not (jump and i in block_of):
            repeats_whole_block = i in block_of and repeat_start < block_of[i][0][1]
            done = (
                block_passes(block_of[i])
                if repeats_whole_block
                else jumps_back.get(i, 0)
            )
            if done < m.play_count - 1:
                jumps_back[i] = jumps_back.get(i, 0) + 1
                i = repeat_start
                continue
            if i not in block_of:
                jumps_back[i] = 0
        if m.end_repeat and i not in block_of:
            repeat_start = i + 1
        if jump:
            jumped.add(i)
            after_jump, jump_origin = True, i
            if "daCapo" in here:
                i = repeat_start = 0
            else:
                i = repeat_start = max((s for s in segnos if s <= i), default=segnos[0])
            continue
        i += 1
    sequence.append(END)
    return sequence


def successors(sequence: Sequence[Optional[int]], n_measures: int) -> List[list]:
    """Turns a performed sequence into a list of successor lists (one per measure, :data:`END` included)."""
    result = [[] for _ in range(n_measures)]
    for k, a in enumerate(sequence[:-1]):
        if a is END:
            continue
        follow = [sequence[k + 1]]
        if follow[0] is END and k + 2 < len(sequence):
            follow.append(sequence[k + 2])  # the piece may end here or go on
        for b in follow:
            if b not in result[a]:
                result[a].append(b)
    return result


def infer_next(measures: Sequence[MeasureStructure]) -> List[list]:
    """Returns, for each measure, the 0-based indices of the measures that can follow it (:data:`END` for the end)."""
    return successors(perform(measures), len(measures))
