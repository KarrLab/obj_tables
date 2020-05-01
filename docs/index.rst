`ObjTables` documentation
================================================

`ObjTables` is a toolkit for using schemas to model collections of tables that represent complex datasets, combining the ease of use of Excel with the rigor and power of schemas.

`ObjTables` makes it easy to:

* Use collections of tables (e.g., an Excel workbook) to represent complex data consisting of multiple related objects of multiple types (e.g., rows of worksheets), each with multiple attributes (e.g., columns).
* Use complex data types (e.g., numbers, strings, numerical arrays, symbolic mathematical expressions, chemical structures, biological sequences, etc.) within tables.
* Use Excel as a graphical interface for viewing and editing complex datasets.
* Use embedded tables and grammars to encode relational information into columns and groups of columns of tables.
* Define clear schemas for tabular datasets.
* Use schemas to rigorously validate tabular datasets.
* Use schemas to parse tabular datasets into data structures for further analysis in languages such as Python.
* Compare, merge, split, revision, and migrate tabular datasets.

The `ObjTables` toolkit includes five components:

* Format for schemas for tabular datasets
* Numerous data types
* Format for tabular datasets
* Software tools for parsing, validating, and manipulating tabular datasets
* Python package for more flexibility and anal

Please see https://www.objtables.org for an overview of `ObjTables` and https://sandbox.karrlab.org/tree/obj_tables for interactive tutorials for the `ObjTables` Python API. This website contains documentation for `ObjTables` migrations and the `ObjTables` Python API.


Contents
--------

.. toctree::
   :maxdepth: 3
   :numbered:

   installation.rst
   migration.rst
   API documentation <source/modules.rst>
   about.rst
