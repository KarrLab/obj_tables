Data migration over schema versions
=============================================

Migration overview
---------------------
Consider some data whose structure (data model) is defined by a schema. For example,
the structure of an SQL database is defined by a schema written in the SQL
Data Definition Language. When the schema is changed then existing data must be changed so that its structure still complies with the schema. This is called data *migration*. 
Many systems, including databases, and web software frameworks provide tools that support automated data migration.

Packages that use Object Model (:obj:`obj_model`) store data in Excel, csv or tsv files. The structure of data in a file is defined by a schema that uses (:obj:`obj_model`. The Object Model *migration* module enables semi-automated migration of these data files.

This page provides an overview of the concepts of Object Model migration and detailed instructions on how to configure and use it.

Migration concepts 
----------------------------------------------
Object Model migration avoids the large and tedious manual effort that's needed when a schema is changed
and multiple data files use the schema to define their structure. 

Migration assumes that data files that are migrated and the schemas that define their structure
are stored in Git repositories. The repository storing the data files is called the *data repo*
while the repository containing the schema is the *schema repo*.
While these are typically distinct repositories, migration also supports the situation in which
one repository serves as both the *data repo* and the *schema repo*.

Migration further assumes that a schema is stored in a single Python file called
the *schema* file, and its name doesn't change over the time span of a migration.
Because it's stored in a Git repository, its versions are
recorded in a directed acyclic graph of commits in the repository. These commits are
used by migration to determine changes in the *schema*. Figure 1 below illustrates these concepts.

Figure here

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



Configuring migration
----------------------------------------------

Both *schema repos* and *data repos* contain user-created configuration files and
small programs that simplify migration, as listed in Tables 1 and 2 below.

.. csv-table:: Table 1. Configuration files in *schema repo*s
   :file: ./migration/migrations_rst_tables_schema_repo_config.csv
   :widths: 17, 25, 25, 25, 8
   :header-rows: 1

=========   =======     =============   ==============  ==========
File type	File use	File location	Filename format	File format
=========   =======     =============   ==============  ==========
Data-schema migration configuration file	Configure the migration of a set of files in a *data repo* whose data models are defined by the same schema in a *schema repo*	"Stored in the :obj:`migrations` directory in the *schema repo*, which is automatically created if necessary    data_schema_migration_conf--{}--{}--{}.yaml, where format placeholders are replaced with 1) the name of the *data repo*, 2) the name of the *schema repo*, and 3) a datetime value	yaml
=========   =======     =============   ==============  ==========

Example configuration files

Fields in configuration files

Schema git metadata in data file

Each data file in the *data repo* must contain a *Model* that the version of the *schema repo*
upon which the file depends. This git metadata is stored in a *Model* called *SchemaRepoMetadata`
(or *Schema repo metadata* as a worksheet in a spreadsheet). The metadata specifies the schema's
version with its URL, branch, and commit hash. 
The data file's migration will start at the specified commit in the *schema repo*.

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


