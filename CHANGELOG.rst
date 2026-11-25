=========
Changelog
=========

Unreleased
==========

- Layered comparison of two MeasureMaps of the same music in ``pymeasuremap.compare``: ``compare_layered()`` reports
  whether they are identical, differ in numbering or repeats only, are the same once repeats are written out, can be
  aligned by joining and splitting measures, or are different, and names the measures concerned.
  ``compare_pairs()`` compares many pairs at once and returns a summary table; ``unfold()`` returns the play-through
  of a MeasureMap.
- ``MM compare --other`` and ``MM compare --pairs`` run the layered comparison from the command line, on the files
  passed via ``-f`` or on the pairs listed in a TSV/CSV file. With ``-o``, the summary and the reports are written
  to files.
- The field ``volta`` also takes a list of positive integers for an ending that is played in several passes, e.g.
  ``[1, 2]`` for "1.-2." or ``[1, 3]``. The extraction from music21 writes such a list for a repeat bracket with
  several numbers (it kept only the first one before). ``Measure.get_volta_numbers()`` returns the passes in either
  case.
- A missing output folder passed via ``-o`` is created without asking when the command is not run from a terminal.
- ``Measure.get_actual_length()``: a measure that specifies only ``nominal_length`` now has that length, which
  ``compress()`` and ``decompress()`` use. A measure without any length information raises ``ValueError`` (was
  ``AssertionError``), and so does an invalid time signature such as ``4/0`` (was ``ZeroDivisionError``).
