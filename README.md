[![PyPI package](https://img.shields.io/pypi/v/obj_tables.svg)](https://pypi.python.org/pypi/obj_tables)
[![Documentation](https://readthedocs.org/projects/obj-tables/badge/?version=latest)](https://docs.karrlab.org/obj_tables)
[![Test results](https://circleci.com/gh/KarrLab/obj_tables.svg?style=shield)](https://circleci.com/gh/KarrLab/obj_tables)
[![Test coverage](https://coveralls.io/repos/github/KarrLab/obj_tables/badge.svg)](https://coveralls.io/github/KarrLab/obj_tables)
[![Code analysis](https://api.codeclimate.com/v1/badges/164d7483a2d3bb68b3ca/maintainability)](https://codeclimate.com/github/KarrLab/obj_tables)
[![License](https://img.shields.io/github/license/KarrLab/obj_tables.svg)](LICENSE)
![Analytics](https://ga-beacon.appspot.com/UA-86759801-1/obj_tables/README.md?pixel)

# *ObjTables*: Toolkit for modeling complex datasets with collections of user-friendly tables

*ObjTables* is a toolkit for using schemas to models collections of tables that represent complex datasets, combining the ease of use of Excel with the rigor and power of schemas.

*ObjTables* makes it easy to:

* Use collections of tables (e.g., an Excel workbook) as an interface for viewing and editing complex datasets that consist of multiple related objects that have multiple attributes
* Use complex data types (e.g., numbers, strings, numerical arrays, symbolic mathematical expressions, chemical structures, biological sequences, etc.) within tables,
* Use embedded tables and grammars to encode relational information into columns and groups of columns of tables,
* Define schemas for collections of tables,
* Use schemas to parse collections of tables into Python data structures for further analysis,
* Use schemas to validate the syntax and semantics of collections of tables,
* Conduct operations on complex datasets, such as comparing and merging datasets, and
* Edit schemas and migrate datasets to new versions of schemas.

The *ObjTables* toolkit includes five components:

* **Tabular format for collections of tables.** This includes syntax for declaring which cells represent the names of tables and columns, declaring which entries represent metadata such as the date that a table was updated, and declaring which entries represent comments.
* **Tabular format for schemas for collections of tables.** *ObjTables* schemas capture the format of each table, including the name and data type of each column, which cells represent relationships among the entries in the tables, and constraints on the value of each cell. *ObjTables* supports three modes of encoding relationships into cells in tables.

    * **Columns for relationships among objects represented by entries in tables:** Relationships from one (primary) object to other (related) objects can be captured by (a) incorporating a column that represents a unique *key* for each related object into the table that represents the related objects and (b) encoding the keys for the related objects as a comma-separated list into a column in the table that represents the primary objects.
    * **Embedded tables for *-to-one relationships:** To help users encode complex datasets into a minimal number of tables, *ObjTables* can also encode instances of related classes into groups of columns. *ObjTables* uses merged headings to distinguish these columns.
    * **Embedded grammars for relationships:** To help users encode complex datasets into a minimal number of tables, grammars can be used to encode instances of related classes into a single column. These grammars can be defined declaratively in EBNF format using [Lark](https://lark-parser.readthedocs.io).


* **Python API for defining schemas:** For more flexibility, the Python API can be used to incorporate custom data types into schemas, utilize multiple inheritance, and define custom validation procedures.
* **Numerous data types** including types for mathematics, science, chemoinformatics, and genomics.
* **Software tools for parsing, validating, and manipulating datasets** according to schemas. This includes tools for

    * Pretty printing datasets as Excel workbooks. This enables users to use Excel as a graphical user interface for quickly browsing and editing datasets as described below.
    * Creating templates for datasets.
    * Analyzing, comparing, merging, revisioning, and datasets.
    * Migrating datasets between versions of their schemas.

*ObjTables* enables users to leverage Excel as a graphical user interface for viewing and editing complex datasets. Excel-encoded datasets have the following features:

* **Table of contents:** Optionally, each dataset can include a table that describes the classes represented by the other tables, displays the number of instances of each class, and provides hyperlinks to the other tables.
* **Formatted class titles:** Each table includes a title bar that describes the class. The title bars are formatted, frozen, and protected from editing.
* **Formatted attribute headings:** Each table includes headings for each column and group of columns. The headings are formatted, auto-filtered, frozen, and protected from editing.
* **Inline help for attributes:** *ObjTables* uses Excel comments to embed help information about each attribute into its heading.
* **Select menus for enumerations and relationships:** *ObjTables* provides select menus for each attribute that encodes an enumeration, a one-to-one relationship, or a many-to-one relationship.
* **Instant validation:** *ObjTables* uses Excel to validate several properties of attributes. *Note, due to the limitations of Excel, this provides limited validation. The *ObjTables* software provides far more extensive validation. Furthermore, *ObjTables* makes it easy to implement domain-specific validation at multiple levels.*
* **Hidden extra rows and columns:** To help users focus on the attributes of their classes, *ObjTables* protects and hides all additional rows and columns.


*ObjTables* supports multiple levels of validation of datasets:

* **Attribute validation:** Validations of individual attributes can be defined declaratively (e.g. `string(min_length=8)`). More complex validations can be defined using a Python schema or by implementing custom types of attributes.
* **Instance validation:** Users can implement custom instance-level validations by creating a Python module that implements a schema and implementing the `validate` methods of the classes.
* **Class-level validation:** Most attributes can be constrained to have unique values across all instances (e.g., `string(unique=True)`). Python modules that implement schemas can also capture tuples of attributes that must be unique across all instances of a class. See the [documentation](https://docs.karrlab.org/obj_tables) for more information.

*ObjTables* provides four user interfaces to the software tools:

* **[Web app](https://www.objtables.org)**: The web app enables users to use *ObjTables* without having to install any software.
* **[REST API](https://www.objtables.org/api/)**: The REST API enables users to use *ObjTables* programmatically without having to install any software.
* **Command-line interface**: The command-line interface enables users to use *ObjTables* without having to upload data to this website.
* **Python library**: The Python library enables users to extend *ObjTables* with custom attributes and validation and use *ObjTables* to analyze complex datasets.

## Installation
Please see the [documentation](https://docs.karrlab.org/obj_tables/installation.html).

## Examples, tutorials, and documentation
Please see the [documentation](https://docs.karrlab.org/obj_tables) and [tutorials](https://sandbox.karrlab.org).

## License
*ObjTables* is released under the [MIT license](LICENSE).

## Development team
This package was developed by the [Karr Lab](https://www.karrlab.org) at the Icahn School of Medicine at Mount Sinai in New York, USA.

* [Jonathan Karr](https://www.karrlab.org)
* Arthur Goldberg
* Wolfram Liebermeister
* Bilal Shaikh

## Questions and comments
Please contact the [Karr Lab](mailto:info@karrlab.org) with any questions or comments.
