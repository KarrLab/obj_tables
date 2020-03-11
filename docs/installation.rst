Installation
============

The following is a brief guide to installing `ObjTables`. The `Dockerfile <https://github.com/KarrLab/obj_tables/blob/master/Dockerfile>`_ in the `ObjTables` Git repository contains detailed instructions for how to install `ObjTables` in Ubuntu Linux.

Prerequisites
--------------------------

First, install the following third-party packages:

* `ChemAxon Marvin <https://chemaxon.com/products/marvin>`_ (optional): to calculate major protonation and tautomerization states

    * `Java <https://www.java.com>`_ >= 1.8

* `Git <https://git-scm.com/>`_ (optional): to revision schemas and datasets
* `Graphviz <https://www.graphviz.org/>`_ (optional): to generate UML diagrams of schemas
* `Open Babel <http://openbabel.org>`_  (optional): to represent and validate chemical structures
* `Pip <https://pip.pypa.io>`_ >= 18.0
* `Python <https://www.python.org>`_ >= 3.6

To use ChemAxon Marvin, set ``JAVA_HOME`` to the path to your Java virtual machine (JVM) and add Marvin to the Java class path::

   export JAVA_HOME=/usr/lib/jvm/default-java
   export CLASSPATH=$CLASSPATH:/opt/chemaxon/marvinsuite/lib/MarvinBeans.jar

Installing the latest release from PyPI
---------------------------------------
Second, we recommend that users run the following command to install the latest release of `ObjTables` from PyPI::

    pip install obj_tables

Installing the latest revision from GitHub
------------------------------------------
We recommend that developers use the following commands to install the latest revision from GitHub::

    pip install git+https://github.com/KarrLab/pkg_utils.git#egg=pkg_utils
    pip install git+https://github.com/KarrLab/wc_utils.git#egg=wc_utils[chem]
    pip install git+https://github.com/KarrLab/bpforms.git#egg=bpforms
    pip install git+https://github.com/KarrLab/bcforms.git#egg=bcforms
    pip install git+https://github.com/KarrLab/obj_tables.git#egg=obj_tables

Installing the optional features
--------------------------------
`ObjTables` includes several optional features:

* `bio`: Biology attributes for sequences, sequence features, and frequency position matrices (:py:`obj_tables.bio`)
* `chem`: Chemistry attributes for chemical formulas and structures (:py:`obj_tables.chem`)
* `grammar`: Encoding/decoding objects and their relationships into and out of individual cells in tables
* `math`: Mathematics attributes for arrays, tables, and symbolic expressions (:py:`obj_tables.math`)
* `rest`: REST API
* `revisioning`: Revisioning schemas and data sets with Git
* `sci`: Science attributes for units, quantities, uncertainty, ontology terms, and references (:py:`obj_tables.sci`)
* `viz`: Methods to generate UML diagrams of schemas

These features can be installed by installing `ObjTables` with the desired options. For example, the `bio` and `chem` features can installed by running one of the following commands::

    pip install obj_tables[bio,chem]
    pip install git+https://github.com/KarrLab/obj_tables.git#egg=obj_tables[bio,chem]
