[![PyPI package](https://img.shields.io/pypi/v/obj_tables.svg)](https://pypi.python.org/pypi/obj_tables)
[![Documentation](https://readthedocs.org/projects/obj-tables/badge/?version=latest)](https://docs.karrlab.org/obj_tables)
[![Test results](https://circleci.com/gh/KarrLab/obj_tables.svg?style=shield)](https://circleci.com/gh/KarrLab/obj_tables)
[![Test coverage](https://coveralls.io/repos/github/KarrLab/obj_tables/badge.svg)](https://coveralls.io/github/KarrLab/obj_tables)
[![Code analysis](https://api.codeclimate.com/v1/badges/164d7483a2d3bb68b3ca/maintainability)](https://codeclimate.com/github/KarrLab/obj_tables)
[![License](https://img.shields.io/github/license/KarrLab/obj_tables.svg)](LICENSE)
![Analytics](https://ga-beacon.appspot.com/UA-86759801-1/obj_tables/README.md?pixel)

# *ObjTables*: Toolkit for working with complex data as collections of user-friendly tables with the ease of spreadsheets, the rigor of schemas, and the power object-oriented programming

*ObjTables* is a toolkit which makes it easy to use spreadsheets (e.g., XLSX workbooks) to work with complex datasets by combining spreadsheets with rigorous schemas and an object-relational mapping system (ORM; similar to Active Record (Ruby), Django (Python), Doctrine (PHP), Hibernate (Java), Propel (PHP), SQLAlchemy (Python), etc.). This combination enables users to use programs such as Microsoft Excel, LibreOffice Calc, and OpenOffice Calc to view and edit spreadsheets and use schemas and the *ObjTables* software to validate the syntax and semantics of datasets, compare and merge datasets, and parse datasets into object-oriented data structures for further querying and analysis with languages such as Python.

*ObjTables* makes it easy to:

* Use collections of tables (e.g., an XLSX workbook) to represent complex data consisting of multiple related objects of multiple types (e.g., rows of worksheets), each with multiple attributes (e.g., columns).
* Use complex data types (e.g., numbers, strings, numerical arrays, symbolic mathematical expressions, chemical structures, biological sequences, etc.) within tables.
* Use progams such as Excel and LibreOffice as a graphical interface for viewing and editing complex datasets.
* Use embedded tables and grammars to encode relational information into columns and groups of columns of tables.
* Define clear schemas for tabular datasets.
* Use schemas to rigorously validate tabular datasets.
* Use schemas to parse tabular datasets into data structures for further analysis in languages such as Python.
* Compare, merge, split, revision, and migrate tabular datasets.

The *ObjTables* toolkit includes five components:

* Format for schemas for tabular datasets
* Numerous data types
* Format for tabular datasets
* Software tools for parsing, validating, and manipulating tabular datasets
* Python package for more flexibility and analysis

Please see https://objtables.org for more information.

## Installing the command-line program and Python API
Please see the [documentation](https://docs.karrlab.org/obj_tables/installation.html).

## Examples, tutorials, and documentation
Please see the [user documentation](https://www.objtables.org), [developer documentation](https://docs.karrlab.org/obj_tables), and [tutorials](https://sandbox.karrlab.org).

## License
*ObjTables* is released under the [MIT license](LICENSE).

## Development team
*ObjTables* was developed by the [Karr Lab](https://www.karrlab.org) at the Icahn School of Medicine at Mount Sinai in New York, USA and the [Applied Mathematics and Computer Science, from Genomes to the Environment research unit](https://maiage.inra.fr/) at the [National Research Institute for Agriculture, Food and Environment](https://www.inrae.fr/en/centres/ile-france-jouy-josas-antony/) in Jouy en Josas, FR.

* [Jonathan Karr](https://www.karrlab.org)
* [Arthur Goldberg](https://www.mountsinai.org/profiles/arthur-p-goldberg)
* [Wolfram Liebermeister](http://genome.jouy.inra.fr/~wliebermeis/index_en.html)
* [John Sekar](https://www.linkedin.com/in/john-sekar/)
* [Bilal Shaikh](https://www.bshaikh.com)

## Questions and comments
Please contact the [developers](mailto:info@objtables.org) with any questions or comments.
