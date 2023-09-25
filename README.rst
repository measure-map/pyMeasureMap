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
