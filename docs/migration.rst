Data migration over schema versions
=============================================

Migration overview
---------------------
Consider some data whose structure (data model) is defined by a schema. For example,
the structure of an SQL database is defined by a schema written in the SQL
Data Definition Language. When the schema is changed then existing data must be changed so that its structure still complies with the schema. This is called data *migration*. 
Many systems, including databases, and web software frameworks provide tools that support automated data migration.

Packages that use Object Model (:obj:`obj_model`) store data in Excel, csv or tsv files. The structure of data in a file is defined by a schema that uses :obj:`obj_model`. The Object Model *migration* module enables semi-automated migration of these data files.

This page provides an overview of the concepts of Object Model migration and detailed instructions on how to configure and use it.

Migration concepts 
----------------------------------------------
Object Model migration avoids the potentially large, tedious and error-prone manual effort that's needed when a schema is changed
and multiple data files use the schema to define their structure.

Migration assumes that data files whare are migrated and the schemas that define their structure
are stored in Git repositories. The repository storing the data files is called the *data repo*
while the repository containing the schema is the *schema repo*.
While these are typically distinct repositories, migration also supports the situation in which
one repository serves as both the *data repo* and the *schema repo*.

Migration further assumes that a schema is stored in a single Python file called
the *schema* file, and its name doesn't change over the time span of a migration.
Because it's stored in a Git repository, its versions are
recorded in a directed acyclic graph of commits in the repository. These commits are
used by migration to determine changes in the *schema*. Figure 1 below illustrates these concepts.

.. image:: migration/figures/migration_example_figure.svg
  :width: 600
  :alt: Example data file migration

Figure 1. Example Object Model data migration. We illustrate the migration of file
:obj:`biomodel_x.xlsx`. Three Git repositories are involved: :obj:`obj_model`, :obj:`wc_lang`, and :obj:`bio_modelx`.
As time increases up, within a repository later commits depend on earlier commits.
(Only selected dependencies are illustrated.)
:obj:`wc_lang` is a schema repo, and :obj:`bio_modelx` is a data repo that uses :obj:`wc_lang`.
The earliest illustrated commit of :obj:`bio_modelx` contains a version of :obj:`biomodel_x.xlsx` that depends on
the earliest commit of :obj:`wc_lang`, which depends on the earliest commit of :obj:`obj_model` (dashed arrows).
:obj:`wc_lang` is updated twice, to produce its latest commit. A configured migration automatically
updates :obj:`biomodel_x.xlsx` so that it's consistent with the latest commit of :obj:`wc_lang` (solid purple arrow).

(todo: distinguish schema & data repos by color)

Many types of changes can be applied to a schema:

* Add a :obj:`obj_model.core.Model` (henceforth, *Model*) definition
* Remove a *Model* definition
* Rename a *Model* definition
* Add an attribute to a *Model*
* Remove an attribute from a *Model*
* Rename an attribute of a *Model*
* Apply another type of changes to a *Model*

Migration automatically handles all types of changes except the last one.
Adding and removing *Model* definitions and adding and removing attributes from *Model*s are
migrated completely automatically. Renaming *Model* definitions and attributes of *Model*s requires
configuration information from a user, as described below.

Other types of modifications can be automated by custom Python transformation programs,
which are also described below.

This code contains an example *existing* schema:

.. literalinclude:: ./migration/existing_schema.py
  :language: Python

And this example shows a *changed* version of the schema above, with comments that document the changes:

.. literalinclude:: ./migration/changed_schema.py
  :language: Python

The instructions below will use these examples.

Configuring migration
----------------------------------------------

Both *schema repos* and *data repos* contain user-created configuration files and
small programs that simplify migration, as listed in Tables 1 and 2 below.

.. csv-table:: Configuration files in schema repos
   :file: ./migration/migrations_rst_tables_schema_repo_config.csv
   :widths: 12, 25, 25, 25, 8
   :header-rows: 1

.. csv-table:: Configuration file in data repos
   :file: migration/migrations_rst_tables_data_repo_config.csv
   :widths: 12, 30, 25, 25, 8
   :header-rows: 1


Example configuration files
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This example *Schema changes* file documents the changes between the *existing* and *changed*
schema versions above:

.. literalinclude:: migration/schema_changes_2019-03-26-20-16-45_820a5d1.yaml
  :language: YAML

It contains the hash of a git commit, which must be the last commit that changed the schema
between the *existing* and *changed*
schema versions. That is, the commit identified in the *Schema changes* file must depend on all
commits that changed the schema since the commit identified by the previous *Schema changes* file.
The hash's prefix also appears in the file's name.

Templates for *Schema changes* files are created by the XXX command, described below.

This example *transformations* file converts the floats in attribute :obj:`Test.size` into ints:

.. literalinclude:: migration/example_transformation.py
  :language: Python

Transformations are subclasses of :obj:`obj_model.migrate.MigrationWrapper`. `Model` instances can
be converted before or after migration, or both. 
The :obj:`prepare_existing_models` method converts models before migration, while 
the :obj:`modify_migrated_models` method converts them after migration. Each of these
methods has the same signature.

A :obj:`custom_io_classes.py` file in a *schema repo* gives Object Model handles to the schema's
:obj:`Reader` and/or :obj:`Writer` classes so they can be used to read and/or write data files
that use the schema.

This example ``custom_io_classes.py`` file configures Object Model that use :obj:`wc_lang` to use
its :obj:`Reader`:

.. literalinclude:: migration/example_transformation.py
  :language: Python

This example *Data-schema migration configuration* file xxxx



Schema git metadata in data files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each data file in the *data repo* must contain a *Model* that documents the version of the *schema repo*
upon which the file depends. This git metadata is stored in a *Model* called *SchemaRepoMetadata*
(or *Schema repo metadata* as a worksheet in a spreadsheet). The metadata specifies the schema's
version with its URL, branch, and commit hash. 
The data file's migration will start at the specified commit in the *schema repo*. An example
Schema repo metadata worksheet in an Excel data file is illustrated below:

.. image:: migration/schema_git_metadata.png
  :width: 600
  :alt: Example Schema repo metadata worksheet in an Excel data file

With regard to the *previous* relation between schema changes files, recall that dependencies among commits in a repository are structured as a directed acyclic graph because each commit (except the first) has one or more previously created parents upon which it depends. Migration topologically sorts the commits in a *schema repo* and
then migrates data files from the first *schema changes* file to the last one.
Therefore, *schema changes* files must be located in the dependency graph so that any valid topological sort creates a valid migration sequence. [See the examples in Figure x.]


Migration migrates a data file from the schema commit identified in the file's schema's git metadata to
the last *schema changes* configuration file in the *schema repo*.


Configuring the *schema repo*


Configuring the *data repo*


Using migration
----------------------------------------------
Migration commands are run via the *wc-cli* program on a Unix command line.

Must be able to clone data repo and schema repo



Debugging migration
----------------------------------------------


Limitations
----------------------------------------------


