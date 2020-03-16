`ObjTables` documentation
================================================

`ObjTables` is a toolkit for using schemas to model collections of tables that represent complex datasets, combining the ease of use of Excel with the rigor and power of schemas.

`ObjTables` makes it easy to:

* Use collections of tables (e.g., an Excel workbook) as an interface for viewing and editing complex datasets that consist of multiple related objects that have multiple attributes,
* Use complex data types (e.g., numbers, strings, numerical arrays, symbolic mathematical expressions, chemical structures, biological sequences, etc.) within tables,
* Use embedded tables and grammars to encode relational information into columns and groups of columns of tables,
* Define schemas for collections of tables,
* Use schemas to parse collections of tables into Python data structures for further analysis,
* Use schemas to validate the syntax and semantics of collections of tables,
* Conduct operations on complex datasets, such as comparing and merging objects, and
* Edit schemas and migrate a dataset to a new version of a schema.

Please see https://www.objtables.org for an overview of `ObjTables` and https://sandbox.karrlab.org/tree/obj_tables for interactive tutorials for the `ObjTables` Python API. This website contains documentation for `ObjTables` migrations, the `ObjTables` Python API, and the `ObjTables` source code.


Contents
--------

.. toctree::
   :maxdepth: 3
   :numbered:

   installation.rst
   migration.rst
   API documentation <source/modules.rst>
   about.rst
