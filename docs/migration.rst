Migrating data files across schema versions
=============================================


Migration overview
---------------------
Consider some data whose structure (data model) is defined by a schema. For example,
the structure of an SQL database is defined by a schema written in the SQL
Data Definition Language. When the schema is changed then existing data must be changed so that its structure still complies with the schema. This is called data *migration*. 
Many systems, including databases, web software frameworks and others provide tools that support automated data migration.

With respect to Object Model (:obj:`obj_model`), consider a file (Excel, csv or tsv) that stores data whose structure is defined by an (:obj:`obj_model`) schemas. The `migration` module enables semi-automated migration of these types of files.

This page provides an overview of the concepts of Object Model migration and detailed instructions on how to configure and use it.

Migration concepts 
----------------------------------------------
Migration assumes that files to migrate and (:obj:`obj_model`) schemas that describe them
are stored in Git repositories. These repositories are known as the *data repo* and *schema repo*, respectively.

The basic idea behind Object Model migration is that the structure of one or more files in a data repo is defined by a schema in a schema repo, and that changes to the schema repo require corresponding changes to the files.

Migration also assumes that a schema specified in a *schema repo* is stored in a single Python file whose name does not change over the time span of a migration. We call this file the *schema* file. Because it's stored in a Git repository, its versions are
recorded in a directed acyclic graph of commits in the repository. These commits are
used by migration to determine changes in the *schema* and migrate files in the
*data repo*. These concepts are illustrated in Figure 1 below.

Changes to the schema repo can take many forms:

* Add (:obj:`obj_model.core.Model`) (henceforth, `Model`) definitions
* Remove `Model` definitions
* Rename `Model` definitions
* Add attributes to `Model`s
* Remove attributes from `Model`s
* Rename attributes of `Model`s
* Otherwise modify `Model`s

All of these modifications except the last one are handled automatically. Adding and removing `Model` definitions and adding and removing attributes from `Model`s are
migrated completely automatically. Renaming `Model` definitions and attributes of `Model`s requires configuration information from a user, as described below.

Other types of modifications can be automated by custom Python transformation programs,
which are also described below.

Schema git metadata in data file

Must be able to clone data repo and schema repo


Configuring migration
----------------------------------------------

Both *schema repos* and *data repos* contain user-created configuration files and
small programs that simplify migration, as listed in Tables 1 and 2 below.

.. list-table:: Title 1: Migration configuration files in *schema repos*s
   :widths: 60 60
   :header-rows: 1

   * - File type
     - File use
     - File location
     - Filename format
   * - Schema changes
     - Associated with a specific commit in the *schema repo*; documents the changes in the *schema* since the previous *Schema changes* file
     - Stored in the :obj:`migrations` directory in the *schema repo*, which will be automatically created if necessary
     - :obj:`schema_changes_{}_{}.yaml`, where the {} placeholders are replaced with the file's creation timestamp and the prefix of the commit's git hash, respectively

   * - Row x, column 1: type
     - Row x, column 2: use
     - Row x, column 3: location
     - Row x, column 4: format

With regard to the *previous* relation between schema changes files, recall that dependencies among commits in a repository are structured as a directed acyclic graph because each commit (except the first) has one or more previously created parents upon which it depends. Migration topologically sorts the commits in a *schema repo* and
then migrates data files from the first *schema changes* file to the last one.
Therefore, *schema changes* files must be located in the dependency graph so that any valid topological sort creates a valid migration sequence. [See the examples in Figure x.]





Configuring the *schema repo*


Configuring the *data repo*


Using migration
----------------------------------------------
Migration commands are run via the `wc-cli` program on a Unix command line.



Debugging migration
----------------------------------------------


Limitations
----------------------------------------------


