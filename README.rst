.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. image:: https://api.cirrus-ci.com/github/<USER>/pyMeasureMap.svg?branch=main
        :alt: Built Status
        :target: https://cirrus-ci.com/github/<USER>/pyMeasureMap
    .. image:: https://readthedocs.org/projects/pyMeasureMap/badge/?version=latest
        :alt: ReadTheDocs
        :target: https://pyMeasureMap.readthedocs.io/en/stable/
    .. image:: https://img.shields.io/coveralls/github/<USER>/pyMeasureMap/main.svg
        :alt: Coveralls
        :target: https://coveralls.io/r/<USER>/pyMeasureMap
    .. image:: https://img.shields.io/pypi/v/pyMeasureMap.svg
        :alt: PyPI-Server
        :target: https://pypi.org/project/pyMeasureMap/
    .. image:: https://img.shields.io/conda/vn/conda-forge/pyMeasureMap.svg
        :alt: Conda-Forge
        :target: https://anaconda.org/conda-forge/pyMeasureMap
    .. image:: https://pepy.tech/badge/pyMeasureMap/month
        :alt: Monthly Downloads
        :target: https://pepy.tech/project/pyMeasureMap
    .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
        :alt: Twitter
        :target: https://twitter.com/pyMeasureMap

.. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
    :alt: Project generated with PyScaffold
    :target: https://pyscaffold.org/

|

============
pyMeasureMap
============


    Python implementation of the MeasureMap specification


Usage
=====

#. Clone the repository
#. Install the package:

   * If you only want to use the package, install it with pip::

       pip install .

     (where `.` stands for the directory with your local clone)

   * If you want to run the tests::

       pip install ".[testing]"

   * If you want to contribute, make sure to include `-e` (for editable) and run::

       pip install -e ".[dev]"

Running all tests
-----------------

To run the tests you need a clone of the `aligned_bach_chorales`_ repository. By default, it will be cloned into your
home directory under ``~/git``. To set it up yourself:

   * Clone `aligned_bach_chorales`_ (submodules not required)
   * Point pyMeasureMap's tests to the directory of the clone by setting the constant ``REPOSITORY_PATH`` to the
     directory that includes the ``aligned_bach_chorales`` directory.

To run the tests, head to your pyMeasureMaps clone and run ``tox``.

.. _aligned_bach_chorales: https://github.com/measure-map/aligned_bach_chorales

Command line interface
----------------------

Once the package is installed, the ``MM`` will be available in your commandline. Typing it will print the available
sub-commands.

Extracting measure maps
~~~~~~~~~~~~~~~~~~~~~~~

Type ``MM extract -h`` to print the help with all arguments.

Parsing all files in ``path/to/chorales`` that music21 can parse::

    MM extract -d path/to/corpus                    # creates measure maps next to the parsed files
    MM extract -d path/to/corpus -o path/to/output  # creates measure maps in the specified directory
    MM extract -d path/to/corpus -r "^bwv"          # only parses files that match the regex (i.e., start with "bwv")
    MM extract -d path/to/corpus -x .mxl .xml       # only parses files with the specified extensions

Loading and writing
-------------------


.. code-block:: python

   mm = MeasureMap.from_json_file("path/to/file.mm.json")
   mm.to_json_file("path/to/new_file.mm.json")

Compress a MeasureMap object
----------------------------

.. code-block:: python

   mm = MeasureMap.from_json_file("path/to/file.mm.json")
   compressed = mm.compress()
   compressed.to_json_file("path/to/compressed.mm.json")

Comparing measure maps
----------------------

Two measure maps of the same music often differ: one edition counts the anacrusis as measure 1, another splits a
measure at a repeat sign, a third writes out what the others repeat. The layered comparison tells these cases
apart. It takes a *preferred* measure map as reference and an *other* one, and answers four questions in turn:

#. **count**: Do both have the same number of measures?
#. **fields**: If so, which of the fields that both define are identical, measure by measure?
#. **unfolded**: If the counts or the repeats differ, are the two the same once repeats are written out?
#. **aligned**: If not, which operations turn the other sequence of measures into the preferred one?

The answer is summed up in a verdict:

================================= ===================================================================================
verdict                           meaning
================================= ===================================================================================
``identical``                     same number of measures, all fields defined on both sides are identical
``same_count``                    same number of measures, but no field is defined on both sides
``same_measures``                 same number of measures with the same lengths and time signatures; other fields
                                  (e.g., numbering or repeat signs) differ
``same_count_different_measures`` same number of measures, but some lengths or time signatures differ
``same_when_unfolded``            the numbers of measures differ, but the play-throughs are the same
``alignable``                     the measures are segmented differently: joins and splits are enough to align them
``different``                     the alignment needs insertions, deletions, or changes of length or time signature
================================= ===================================================================================

The operations of an alignment are named from the point of view of the other measure map: ``match``,
``change_length``, ``change_time_signature``, ``join`` (two other measures add up to one preferred measure),
``split`` (one other measure corresponds to two preferred ones), ``insert`` (a preferred measure has no
counterpart), and ``delete`` (an other measure has no counterpart).

Fields that one side does not define are not compared and do not count as differences. A measure map that merely
enumerates measures (say, the measures detected on a scan) can therefore be compared with one that has lengths
and time signatures; the summary says which fields were compared.

In Python:

.. code-block:: python

   from pymeasuremap.compare import compare_layered, compare_pairs

   report = compare_layered("path/to/preferred.mm.json", "path/to/other.mm.json")
   report.verdict          # e.g. 'alignable'
   print(report.to_text()) # the verdict, one line per layer, and the steps of the alignment
   report.summary()        # one flat dictionary, e.g. for a row of a table
   report.measure_table()  # measure-by-measure juxtaposition as a pandas DataFrame

   # many pairs at once: a summary table plus the reports
   summary, reports = compare_pairs(
       [("a/preferred.mm.json", "a/other.mm.json"), ("b/preferred.mm.json", "b/other.mm.json")],
       output_directory="path/to/reports",
   )

``pymeasuremap.compare.unfold()`` returns the play-through of a measure map as a sequence of counts. It follows the
``next`` fields if there are any and otherwise interprets the repeat signs and voltas.

On the command line (``MM compare -h`` prints the help)::

    MM compare -f preferred.mm.json --other other.mm.json  # prints the report
    MM compare -d path/to/corpus --pairs pairs.tsv -o path/to/reports

``pairs.tsv`` contains one pair per row, the path of the preferred measure map in the first column and that of the
other one in the second, separated by tabs or commas, with or without a header row. Relative paths are resolved
against ``-d``. With ``-o``, the command writes ``comparison_summary.tsv`` (one row per pair with the verdict, the
numbers of measures, the compared and the differing fields, and how often each operation occurs) and, for each
pair that is not identical, ``<preferred>_vs_<other>.tsv`` (the measure table) and ``.txt`` (the report).

Without ``--other`` and ``--pairs``, ``MM compare`` runs the older diagnosis: for each file called
``preferred_measure_map.json`` under ``-d`` (or each file passed via ``-f``) it looks for
``other_measure_map.json`` in the same folder and writes the suggested modifications to
``other_modifications.txt`` next to it.

Limitations: repeats within repeats and jumps such as da capo are followed only where ``next`` states them; the
same music notated in different note values (2/2 against 4/4 with halved measures) is reported as ``different``;
where neither lengths nor measure numbers tell which of several equal measures is the surplus one, its reported
position is arbitrary.



.. _pyscaffold-notes:

Making Changes & Contributing
=============================

This project uses `pre-commit`_, please make sure to install it before making any
changes::

    pip install pre-commit
    cd pyMeasureMap
    pre-commit install

It is a good idea to update the hooks to the latest version::

    pre-commit autoupdate

Don't forget to tell your contributors to also install and use pre-commit.

.. _pre-commit: https://pre-commit.com/

Note
====

This project has been set up using PyScaffold 4.5. For details and usage
information on PyScaffold see https://pyscaffold.org/.
