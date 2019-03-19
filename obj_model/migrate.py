#!/usr/bin/env python3
""" Support schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""
import os
import re
import sys
import argparse
import importlib
import importlib.util
from pathlib import Path
import inspect
import copy
import warnings
import yaml
from six import integer_types, string_types
from enum import Enum
from warnings import warn
from pprint import pprint, pformat
import git
import networkx as nx
from networkx.algorithms.dag import topological_sort, ancestors
import tempfile
import datetime

import obj_model
from obj_model import (TabularOrientation, RelatedAttribute, get_models, SlugAttribute, StringAttribute,
    RegexAttribute, UrlAttribute, DateTimeAttribute)
from obj_model.units import UnitAttribute
from obj_model.io import WorkbookReader, IoWarning
import wc_utils
from wc_utils.util.list import det_find_dupes, det_count_elements, dict_by_class
from wc_utils.util.files import normalize_filename
from obj_model.expression import ParsedExpression, ObjModelTokenCodes


# TODOS
# migration integrated into wc_lang & wc_kb
#
# refactor generate_wc_lang_migrator into method in wc_lang called by obj_model
#   define abstract migrator here, and let schema optionally subclass it
# commit schema changes specs
#   one for each commit that changes schema
#   contains commit hash, renamed_models, renamed_attributes, transformations
#   stored in repo 'migrations' directory
#   commit migration spec YAML format, with commit hash in filename
#   migration spec reader: read all migration specs in the 'migrations' directory
#   use in MigrationSpecs
#   automatically prefix sortable date timestamp of commit to migration file
# wc_lang / wc_kb commands to migrate files
#   CLI: migrate file / directory [more]
#   local migration calls obj_model migration
#   by default, migrate to current version, make backups of models & migrate in place
# schema hash in each model file
#   initially, as is in wc_lang models
#   eventually, ideally in a metadata Model
# testing
#   add a few wc_lang versions
# publicize work, in part to get feedback

# todo: final bits of coverage
'''
documentation notes:
a schema must be imported from a self-contained module or a
complete package, as otherwise import statements within the package may use another version of it on sys.path.

Migration is not composable. It should be run independently of other obj_model code.
'''
# todo now
'''
migrate xlsx files in wc_sim to new wc_lang:
1: identify all wc model files in wc_sim, the wc_lang commits that they use, & get those wc_lang versions
2. get the present wc_lang version
3. create a config file for the wc model files
4: migrate them
'''
# todo next: generic transformations in YAML config
# todo: good wc_lang migration example
# todo: does SBML have migration?

# todo: wc_lang migration without a config file
# todo: migration steps for wc_lang commits
# todo: retain or control column and row order
# todo: Preload a schema’s required packages from requirements.txt, and set sys.path to hold just the schema’s directory
# to avoid collisions and enable relative imports
# todo: deleted models: handle automatically (model that's not present in migrated schema or renamed is deleted), or add to config attributes
# todo next: test OneToManyAttribute
# todo next: documentation
# todo next: simply infer the deleted_models

class MigratorError(Exception):
    """ Exception raised for errors in obj_model.migrate

    Attributes:
        message (:obj:`str`): the exception's message
    """
    def __init__(self, message=None):
        super().__init__(message)


class MigrateWarning(UserWarning):
    """ Migrate warning """
    pass


class SchemaModule(object):
    """ Represent and import a schema module

    Attributes:
        module_path (:obj:`str`): path to the module
        abs_module_path (:obj:`str`): absolute path to the module
        directory (:obj:`str`): if the module is in a package, the path to the package's directory;
            otherwise the directory containing the module
        package_name (:obj:`str`): if the module is in a package, the name of the package containing the
            module; otherwise `None`
        module_name (:obj:`str`): the module's module name
    """

    # cached schema modules that have been imported, indexed by full pathnames
    MODULES = {}

    def __init__(self, module_path, dir=None):
        """ Initialize a `SchemaModule`

        Args:
            module_path (:obj:`str`): path to the module
            dir (:obj:`str`, optional): a directory that contains `self.module_path`
        """
        self.module_path = module_path
        self.abs_module_path = normalize_filename(self.module_path, dir=dir)
        self.directory, self.package_name, self.module_name = self.parse_module_path(self.abs_module_path)

    def get_path(self):
        return str(self.abs_module_path)

    @staticmethod
    def parse_module_path(module_path):
        """ Parse the path to a module

        If the module is not in a package, provide its directory and module name.
        If the module is in a package, provide its directory, package name and module name.
        The directory can be used as a `sys.path` entry.

        Args:
            module_path (:obj:`str`): path of a Python module file

        Returns:
            :obj:`tuple`: a triple containing directory, package name and module name, as described
            above. If the module is not in a package, then package name is `None`.

        Raises:
            :obj:`MigratorError`: if `module_path` is not the name of a Python file, or is not a file
        """
        path = Path(module_path)

        if not path.suffixes == ['.py']:
            raise MigratorError("'{}' is not a Python source file name".format(module_path))
        if not path.is_file():
            raise MigratorError("'{}' is not a file".format(module_path))

        # go up directory hierarchy from path and get first directory that does not contain '__init__.py'
        dir = path.parent
        found_package = False
        while True:
            if not dir.joinpath('__init__.py').is_file():
                break
            # exit at / root
            if dir == dir.parent:
                break
            found_package = True
            dir = dir.parent
        if found_package:
            # obtain package name between directory and module
            package_name = str(path.relative_to(dir).parent).replace('/', '.')
            module_name = package_name + '.' + path.stem
            return str(dir), package_name, module_name

        else:
            # obtain directory and module name
            module_directory = path.parent
            module_name = path.stem
            return str(module_directory), None, module_name

    # suffix for munged model names
    # include whitespace so munged Model names cannot collide with actual Model names
    MUNGED_MODEL_NAME_SUFFIX = '_MUNGED WITH SPACES'

    def in_package(self):
        """ Is the schema in a package

        Returns:
            :obj:`bool`: whether the schema is in a package
        """
        return self.package_name is not None

    @staticmethod
    def _munge_model_name(model):
        """ Munge `model`'s name

        Args:
            model (:obj:`obj_model.Model`): a model

        Returns:
            :obj:`str`: a munged name for model, made by appending `SchemaModule.MUNGED_MODEL_NAME_SUFFIX`
        """
        return "{}{}".format(model.__name__, SchemaModule.MUNGED_MODEL_NAME_SUFFIX)

    @staticmethod
    def _unmunge_model_name(model):
        """ Ununge `model`'s name

        Args:
            model (:obj:`obj_model.Model`): a model

        Returns:
            :obj:`str`: an unmunged name for `model`, made by removing the suffix
                `SchemaModule.MUNGED_MODEL_NAME_SUFFIX`

        Raises:
            :obj:`MigratorError`: if `model` isn't munged
        """
        if SchemaModule._model_name_is_munged(model):
            return model.__name__[:-len(SchemaModule.MUNGED_MODEL_NAME_SUFFIX)]
        else:
            raise MigratorError("{} isn't munged".format(model.__name__))

    @staticmethod
    def _model_name_is_munged(model):
        """ Is `model`'s name munged

        Args:
            model (:obj:`obj_model.Model`): a model

        Returns:
            :obj:`bool`: True if `model` is munged
        """
        return model.__name__.endswith("{}".format(SchemaModule.MUNGED_MODEL_NAME_SUFFIX))

    @staticmethod
    def _munge_all_model_names():
        """ Munge the names of all models, so the models cannot be found by name and reused
        """
        for model in get_models():
            model.__name__ = SchemaModule._munge_model_name(model)

    @staticmethod
    def _unmunge_all_munged_model_names():
        """ Unmunge the names of all models so they can be used, inverting `_munge_all_model_names`
        """
        for model in get_models():
            if SchemaModule._model_name_is_munged(model):
                model.__name__ = SchemaModule._unmunge_model_name(model)

    def import_module_for_migration(self, validate=True):
        """ Import a schema in a Python module

        Args:
            validate (:obj:`bool`, optional): whether to validate the module; default is True

        Returns:
            :obj:`Module`: the `Module` loaded from `self.module_path`

        Raises:
            :obj:`MigratorError`: if the schema at `self.module_path` cannot be imported,
                or if validate is True and any related attribute in any model references a model
                    not in the module
        """
        if self.get_path() in self.MODULES:
            return self.MODULES[self.get_path()]

        # temporarily munge names of all models in modules imported for migration so they're not reused
        SchemaModule._munge_all_model_names()

        # copy sys.paths and sys.modules so they can be restored
        sys_attrs = ['path', 'modules']
        saved = {}
        for sys_attr in sys_attrs:
            saved[sys_attr] = getattr(sys, sys_attr).copy()

        try:
            # suspend global check that related attribute names don't clash
            obj_model.core.ModelMeta.CHECK_SAME_RELATED_ATTRIBUTE_NAME = False

            sys.path.insert(0, self.directory)
            module = importlib.import_module(self.module_name)

        except (SyntaxError, ImportError, AttributeError, ValueError, NameError) as e:
            raise MigratorError("'{}' cannot be imported and exec'ed: {}".format(
                self.get_path(), e))
        finally:
            # reset global variable
            obj_model.core.ModelMeta.CHECK_SAME_RELATED_ATTRIBUTE_NAME = True
            # unmunge names of all models in modules imported for migration
            SchemaModule._unmunge_all_munged_model_names()

        # restore sys.path
        sys.path = saved['path']

        # to avoid side effects do not allow changes to sys.modules
        sys.modules = saved['modules']

        if validate:
            errors = self._check_imported_models(module=module)
            if errors:
                raise MigratorError('\n'.join(errors))

        self.MODULES[self.get_path()] = module

        return module

    def _get_model_defs(self, module):
        """ Obtain the `obj_model.Model`s in a module

        Args:
            module (:obj:`Module`): a `Module` containing subclasses of `obj_model.Model`

        Returns:
            :obj:`dict`: the Models in a module

        Raises:
            :obj:`MigratorError`: if no subclasses of `obj_model.Model` are found
        """
        models = {}
        for name, cls in inspect.getmembers(module, inspect.isclass):
            if issubclass(cls, obj_model.core.Model) and \
                not cls in {obj_model.Model, obj_model.abstract.AbstractModel}:
                models[name] = cls
        # ensure that a schema contains some obj_model.Models
        if not models:
            raise MigratorError("No subclasses of obj_model.Model found in '{}'".format(self.abs_module_path))
        return models

    def _check_imported_models(self, module=None):
        """ Check consistency of an imported module

        Args:
            module (:obj:`Module`, optional): a `Module` containing subclasses of `obj_model.Model`;
            if not provided, the module is imported

        Returns:
            :obj:`list`: errors in the module
        """
        module = self.import_module_for_migration() if module is None else module
        model_defs = self._get_model_defs(module)

        # ensure that all RelatedAttributes in all models reference models in the module
        errors = []
        for model_name, model in model_defs.items():
            for attr_name, local_attr in model.Meta.local_attributes.items():

                if isinstance(local_attr.attr, RelatedAttribute):
                    related_class = local_attr.related_class
                    if related_class != model_defs[related_class.__name__]:
                        errors.append("{}.{} references a {}, but it's not the model in module {}".format(
                                model_name, attr_name, related_class.__name__, module.__name__))
        return errors

    def run(self):
        """ Import a schema and provide its `obj_model.Model`s

        Returns:
            :obj:`dict`: the imported Models

        Raises:
            :obj:`MigratorError`: if `self.module_path` cannot be loaded
        """
        module = self.import_module_for_migration()
        return self._get_model_defs(module)

    def __str__(self):
        vals = []
        for attr in ['module_path', 'abs_module_path', 'directory', 'package_name', 'module_name']:
            vals.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(vals)


class Migrator(object):
    """ Support schema migration

    Attributes:
        existing_schema (:obj:`SchemaModule`): the existing schema, and its properties
        migrated_schema (:obj:`SchemaModule`): the migrated schema, and its properties
        existing_defs (:obj:`dict`): `obj_model.Model` definitions of the existing models, keyed by name
        migrated_defs (:obj:`dict`): `obj_model.Model` definitions of the migrated models, keyed by name
        deleted_models (:obj:`set`): model types defined in the existing models but not the migrated models
        renamed_models (:obj:`list` of :obj:`tuple`): model types renamed from the existing to the migrated schema
        models_map (:obj:`dict`): map from existing model names to migrated model names
        renamed_attributes (:obj:`list` of :obj:`tuple`): attribute names renamed from the existing to
            the migrated schema
        renamed_attributes_map (:obj:`dict`): map of attribute names renamed from the existing to the migrated schema
        _migrated_copy_attr_name (:obj:`str`): attribute name used to point existing models to corresponding
            migrated models; not used in any existing model definitions
        transformations (:obj:`dict`): map of transformation types in `SUPPORTED_TRANSFORMATIONS` to callables
    """

    SCALAR_ATTRS = ['deleted_models', '_migrated_copy_attr_name']
    COLLECTIONS_ATTRS = ['existing_defs', 'migrated_defs', 'renamed_models', 'models_map',
        'renamed_attributes', 'renamed_attributes_map']

    # default suffix for a migrated model file
    MIGRATE_SUFFIX = '_migrated'

    # modules being used for migration, indexed by full pathname
    # Migrator does not need or support packages
    modules = {}

    # prefix of attribute name used to connect existing and migrated models during migration
    MIGRATED_COPY_ATTR_PREFIX = '__migrated_copy'

    # the name of the attribute used in expression Models to hold their ParsedExpressions
    PARSED_EXPR = '_parsed_expression'

    # supported transformations
    PREPARE_EXISTING_MODELS = 'PREPARE_EXISTING_MODELS'
    MODIFY_MIGRATED_MODELS = 'MODIFY_MIGRATED_MODELS'
    SUPPORTED_TRANSFORMATIONS = [
        # A callable w the signature f(migrator, existing_models), where `migrator` is a Migrator doing
        # a migration, and `existing_models` is a list of all existing models. It is executed immediately
        # after the existing models have been read. The callable may alter any of the existing models.
        PREPARE_EXISTING_MODELS,
        # A callable w the signature f(migrator, migrated_models), where `migrator` is a Migrator doing
        # a migration, and `migrated_models` is a list of all migrated models. It is executed immediately
        # after all models have been migrated. The callable may alter any of the migrated models.
        MODIFY_MIGRATED_MODELS
    ]

    def __init__(self, existing_defs_file=None, migrated_defs_file=None, renamed_models=None,
        renamed_attributes=None, transformations=None):
        """ Construct a Migrator

        Args:
            existing_defs_file (:obj:`str`, optional): path of a file containing existing Model definitions
            migrated_defs_file (:obj:`str`, optional): path of a file containing migrated Model definitions;
                filenames optional so that `Migrator` can use models defined in memory
            renamed_models (:obj:`list` of :obj:`tuple`, optional): model types renamed from the existing to the
                migrated schema; has the form `[('Existing_1', 'Migrated_1'), ..., ('Existing_n', 'Migrated_n')]`,
                where `('Existing_i', 'Migrated_i')` indicates that existing model `Existing_i` is
                being renamed into migrated model `Migrated_i`.
            renamed_attributes (:obj:`list` of :obj:`tuple`, optional): attribute names renamed from the existing
                to the migrated schema; a list of tuples of the form
                `(('Existing_Model_i', 'Existing_Attr_x'), ('Migrated_Model_j', 'Migrated_Attr_y'))`,
                which indicates that `Existing_Model_i.Existing_Attr_x` will migrate to
                `Migrated_Model_j.Migrated_Attr_y`.
            transformations (:obj:`dict`, optional): map of transformation types in `SUPPORTED_TRANSFORMATIONS`
                to callables
        """
        self.existing_schema = SchemaModule(existing_defs_file) if existing_defs_file else None
        self.migrated_schema = SchemaModule(migrated_defs_file) if migrated_defs_file else None
        self.renamed_models = renamed_models if renamed_models else []
        self.renamed_attributes = renamed_attributes if renamed_attributes else []
        self.transformations = transformations

    def _load_defs_from_files(self):
        """ Initialize a `Migrator`s model definitions from files

        Distinct from `prepare` so most of `Migrator` can be tested with models defined in code

        Returns:
            :obj:`list` of :obj:`obj_model.Model`: the `Model`s in `self.module_path`
        """
        if self.existing_schema:
            self.existing_defs = self.existing_schema.run()
        if self.migrated_schema:
            self.migrated_defs = self.migrated_schema.run()
        return self

    def _get_migrated_copy_attr_name(self):
        """ Obtain name of attribute used in an existing model to reference its migrated model

        Returns:
            :obj:`str`: attribute name for a migrated copy
        """
        max_len = 0
        for existing_model_def in self.existing_defs.values():
            for attr in existing_model_def.Meta.attributes.values():
                max_len = max(max_len, len(attr.name))
        return "{}{}".format(Migrator.MIGRATED_COPY_ATTR_PREFIX,
            '_' * (max_len + 1 - len(Migrator.MIGRATED_COPY_ATTR_PREFIX)))

    @staticmethod
    def _validate_transformations(transformations):
        """ Validate transformations

        Ensure that transformations is a dict of callables

        Args:
            transformations (:obj:`object`): a transformations

        Returns:
            :obj:`list` of `str`: errors in `transformations`, if any
        """
        errors = []
        if transformations:
            if not isinstance(transformations, dict):
                return ["transformations should be a dict, but it is a(n) '{}'".format(type(
                    transformations).__name__)]
            if not set(transformations).issubset(Migrator.SUPPORTED_TRANSFORMATIONS):
                errors.append("names of transformations {} aren't a subset of the supported "
                    "transformations {}".format(set(transformations), set(Migrator.SUPPORTED_TRANSFORMATIONS)))
            for transform_name, transformation in transformations.items():
                if not callable(transformation):
                    errors.append("value for transformation '{}' is a(n) '{}', which isn't callable".format(
                        transform_name, type(transformation).__name__))
        return errors

    def _validate_renamed_models(self):
        """ Validate renamed models

        Ensure that renamed models:
        * properly reference the existing and migrated schemas, and
        * don't use an existing or migrated model in more than one mapping

        If the renamed models validate, then create a map from existing to migrated models.

        Returns:
            :obj:`list` of `str`: errors in the renamed models
        """
        self.models_map = {}
        errors = []
        # check renamed models
        for existing_model, migrated_model in self.renamed_models:
            if existing_model not in self.existing_defs:
                errors.append("'{}' in renamed models not an existing model".format(existing_model))
            if migrated_model not in self.migrated_defs:
                errors.append("'{}' in renamed models not a migrated model".format(migrated_model))
        duped_existing_models = det_find_dupes([existing_model for existing_model, _ in self.renamed_models])
        if duped_existing_models:
                errors.append("duplicated existing models in renamed models: '{}'".format(duped_existing_models))
        duped_migrated_models = det_find_dupes([migrated_model for _, migrated_model in self.renamed_models])
        if duped_migrated_models:
                errors.append("duplicated migrated models in renamed models: '{}'".format(duped_migrated_models))
        if errors:
            return errors

        # create self.models_map which maps existing model names to migrated model names
        # assumes that existing and migrated models with the same name correspond unless they're specified
        # in `self.renamed_models` or not migrated
        self.models_map = dict(self.renamed_models)
        for existing_model in self.existing_defs:
            if existing_model not in self.models_map and existing_model in self.migrated_defs:
                self.models_map[existing_model] = existing_model

        return errors

    def _validate_renamed_attrs(self):
        """ Validate renamed attributes

        Ensure that renamed attributes:
        * properly reference the existing and migrated schemas, and
        * don't use an existing or migrated attribute in more than one mapping

        If the renamed attributes validate, create a map from existing to migrated attributes.

        Returns:
            :obj:`list` of `str`: errors in the renamed attributes
        """
        self.renamed_attributes_map = {}
        errors = []

        # check renamed attributes
        for (existing_model, existing_attr), (migrated_model, migrated_attr) in self.renamed_attributes:
            if existing_model not in self.existing_defs or \
                existing_attr not in self.existing_defs[existing_model].Meta.attributes:
                errors.append("'{}.{}' in renamed attributes not an existing model.attribute".format(
                    existing_model, existing_attr))
            if migrated_model not in self.migrated_defs or \
                migrated_attr not in self.migrated_defs[migrated_model].Meta.attributes:
                errors.append("'{}.{}' in renamed attributes not a migrated model.attribute".format(
                    migrated_model, migrated_attr))
            # renamed attributes must be consistent with renamed models
            # i.e., if an attribute is renamed A.x -> B.y then model A must be renamed A -> B
            if existing_model not in self.models_map or \
                migrated_model != self.models_map[existing_model]:
                errors.append("renamed attribute '{}.{} -> {}.{}' not consistent with renamed models".format(
                    existing_model, existing_attr, migrated_model, migrated_attr))
        duped_existing_attributes = det_find_dupes([existing_attr for existing_attr, _ in self.renamed_attributes])
        if duped_existing_attributes:
                errors.append("duplicated existing attributes in renamed attributes: '{}'".format(
                    duped_existing_attributes))
        duped_migrated_attributes = det_find_dupes([migrated_attr for _, migrated_attr in self.renamed_attributes])
        if duped_migrated_attributes:
                errors.append("duplicated migrated attributes in renamed attributes: '{}'".format(
                    duped_migrated_attributes))

        if errors:
            return errors

        # create self.renamed_attributes_map which maps renamed existing model, attribute pairs to
        # their corresponding migrated model, attribute pairs
        self.renamed_attributes_map = dict(self.renamed_attributes)
        return errors

    def _get_mapped_attribute(self, existing_class, existing_attribute):
        """ Get the corresponding migrated class and attribute for the existing class and attribute

        Args:
            existing_class (:obj:`obj_model.core.ModelMeta` or :obj:`str`): an existing class
            existing_attribute (:obj:`obj_model.core.ModelMeta` or :obj:`str`): an attribute in
                `existing_class`

        Returns:
            :obj:`tuple` of `str`: the pair (migrated model name, migrated attr name); return (None, None)
                if the existing class and attribute do not map to a migrated class and attribute
        """

        # convert existing_class and existing_attribute to strings
        if isinstance(existing_class, obj_model.core.ModelMeta):
            existing_class = existing_class.__name__
        if isinstance(existing_attribute, obj_model.Attribute):
            existing_attribute = existing_attribute.name

        # try to map existing_class, existing_attribute in renamed attributes
        if (existing_class, existing_attribute) in self.renamed_attributes_map:
            return self.renamed_attributes_map[(existing_class, existing_attribute)]

        # otherwise try to map existing_class as an unchanged model in self.models_map
        if existing_class in self.models_map:
            migrated_class = self.models_map[existing_class]
            if existing_attribute in self.migrated_defs[migrated_class].Meta.attributes:
                return (migrated_class, self.migrated_defs[migrated_class].Meta.attributes[existing_attribute].name)

        return (None, None)

    def prepare(self):
        """ Prepare for migration

        Raises:
            :obj:`MigratorError`: if renamings are not valid, or
                inconsistencies exist between corresponding existing and migrated classes
        """
        # load schemas from files
        self._load_defs_from_files()

        # validate transformations
        self._validate_transformations(self.transformations)

        # validate model and attribute rename specifications
        errors = self._validate_renamed_models()
        if errors:
            raise MigratorError('\n'.join(errors))
        errors = self._validate_renamed_attrs()
        if errors:
            raise MigratorError('\n'.join(errors))

        # find deleted models
        used_models = set([existing_model for existing_model in self.models_map])
        self.deleted_models = set(self.existing_defs).difference(used_models)

        # check that corresponding models in existing and migrated are consistent
        inconsistencies = []
        for existing_model, migrated_model in self.models_map.items():
            inconsistencies.extend(self._get_inconsistencies(existing_model, migrated_model))
        if inconsistencies:
            raise MigratorError('\n' + '\n'.join(inconsistencies))

        # get attribute name not used in existing model definitions so that existing models can point to migrated models
        self._migrated_copy_attr_name = self._get_migrated_copy_attr_name()

    def _get_inconsistencies(self, existing_model, migrated_model):
        """ Detect inconsistencies between `existing_model` and `migrated_model` model classes

        Detect inconsistencies between `existing_model` and `migrated_model`. Inconsistencies arise if the loaded `existing_model`
        or `migrated_model` definitions are not consistent with their model or attribute renaming specifications
        or with each other.

        Args:
            existing_model (:obj:`str`): name of an existing model class
            migrated_model (:obj:`str`): name of the corresponding migrated model class

        Returns:
            :obj:`list`: inconsistencies between existing_model_cls and migrated_model_cls; an empty list if
                no inconsistencies exist
        """
        inconsistencies = []

        # constraint: existing_model and migrated_model must be available in their respective model definitions
        path = "'{}'".format(self.existing_schema.get_path()) if self.existing_schema \
            else 'existing models definitions'
        if existing_model not in self.existing_defs:
            inconsistencies.append("existing model {} not found in {}".format(existing_model, path))
        path = "'{}'".format(self.migrated_schema.get_path()) if self.migrated_schema \
            else 'migrated models definitions'
        if migrated_model not in self.migrated_defs:
            inconsistencies.append("migrated model {} corresponding to existing model {} not found in {}".format(
                migrated_model, existing_model, path))
        if inconsistencies:
            # return these inconsistencies because they prevent checks below from running accurately
            return inconsistencies

        # constraint: existing_model and migrated_model must be have the same type, which will be obj_model.core.ModelMeta
        existing_model_cls = self.existing_defs[existing_model]
        migrated_model_cls = self.migrated_defs[migrated_model]
        if type(existing_model_cls) != type(migrated_model_cls):
            inconsistencies.append("type of existing model '{}' doesn't equal type of migrated model '{}'".format(
                type(existing_model_cls).__name__, type(migrated_model_cls).__name__))

        # constraint: names of existing_model and migrated_model classes must match their names in the models map
        if existing_model_cls.__name__ != existing_model:
            inconsistencies.append("name of existing model class '{}' not equal to its name in the models map '{}'".format(
                existing_model_cls.__name__, existing_model))
        if migrated_model_cls.__name__ != migrated_model:
            inconsistencies.append("name of migrated model class '{}' not equal to its name in the models map '{}'".format(
                migrated_model_cls.__name__, migrated_model))
        migrated_model_cls = self.migrated_defs[migrated_model]
        expected_migrated_model_name = self.models_map[existing_model]
        if migrated_model_cls.__name__ != expected_migrated_model_name:
            inconsistencies.append("models map says '{}' migrates to '{}', but _get_inconsistencies parameters "
                "say '{}' migrates to '{}'".format(existing_model, expected_migrated_model_name, existing_model,
                    migrated_model))
        if inconsistencies:
            # given these inconsistencies the checks below would not be informative
            return inconsistencies

        # constraint: the types of attributes in existing_model and migrated_model classes must match
        for existing_attr_name, existing_attr in existing_model_cls.Meta.attributes.items():
            migrated_class, migrated_attr = self._get_mapped_attribute(existing_model, existing_attr_name)
            # skip if the attr isn't migrated
            if migrated_attr:
                migrated_attr = migrated_model_cls.Meta.attributes[migrated_attr]
                if type(existing_attr).__name__ != type(migrated_attr).__name__:
                    inconsistencies.append("existing attribute {}.{} type {} differs from its "
                        "migrated attribute {}.{} type {}".format(existing_model, existing_attr_name,
                        type(existing_attr).__name__, migrated_class, migrated_attr, type(migrated_attr).__name__))
        if inconsistencies:
            # given these inconsistencies the checks below would not be informative
            return inconsistencies

        # constraint: related names and types of related attributes in existing_model and migrated_model classes must match
        related_attrs_to_check = ['related_name', 'primary_class', 'related_class']
        for existing_attr_name, existing_attr in existing_model_cls.Meta.attributes.items():
            migrated_class, migrated_attr = self._get_mapped_attribute(existing_model, existing_attr_name)
            if migrated_attr and isinstance(existing_attr, obj_model.RelatedAttribute):
                migrated_attr = migrated_model_cls.Meta.attributes[migrated_attr]
                for rel_attr in related_attrs_to_check:
                    existing_rel_attr = getattr(existing_attr, rel_attr)
                    migrated_rel_attr = getattr(migrated_attr, rel_attr)
                    if isinstance(existing_rel_attr, str) and isinstance(migrated_rel_attr, str):
                        if existing_rel_attr != migrated_rel_attr:
                            inconsistencies.append("{}.{}.{} is '{}', which differs from the migrated value "
                                "of {}.{}.{}, which is '{}'".format(existing_model, existing_attr_name, rel_attr,
                                existing_rel_attr, migrated_class, migrated_attr, rel_attr, migrated_rel_attr))
                    else:
                        # the attributes are models
                        existing_rel_attr_name = existing_rel_attr.__name__
                        migrated_rel_attr_name = migrated_rel_attr.__name__
                        if existing_rel_attr_name in self.deleted_models:
                            inconsistencies.append("existing model '{}' is not migrated, "
                                "but is referenced by migrated attribute {}.{}".format(existing_rel_attr_name,
                                migrated_class, migrated_attr))
                        else:
                            expected_migrated_rel_attr = self.models_map[existing_rel_attr_name]
                            if migrated_rel_attr_name != expected_migrated_rel_attr:
                                inconsistencies.append("{}.{}.{} is '{}', which migrates to '{}', but it "
                                    "differs from {}.{}.{}, which is '{}'".format(
                                    existing_model, existing_attr_name, rel_attr, existing_rel_attr_name, expected_migrated_rel_attr,
                                    migrated_class, migrated_attr, rel_attr, migrated_rel_attr_name))
        return inconsistencies

    def _get_existing_model_order(self, existing_file):
        """ Obtain the sequence in which models appear in the source file

        First determine the order of existing model types in worksheets in the source file. However, the
        mapping of some worksheets to models may be ambiguous. Then map the order to the existing models
        that will migrate.

        Args:
            existing_file (:obj:`str`): pathname of file being migrated

        Returns:
            :obj:`list` of `obj_model.core.ModelMeta`: existing models in the same order as worksheets
                in `existing_file`, followed by existing models with ambiguous sheet names
        """
        _, ext = os.path.splitext(existing_file)
        utils_reader = wc_utils.workbook.io.get_reader(ext)(existing_file)
        utils_reader.initialize_workbook()
        sheet_names = utils_reader.get_sheet_names()

        existing_models_migrating = [self.existing_defs[model_name] for model_name in self.models_map.keys()]

        # detect sheets that cannot be unambiguously mapped
        ambiguous_sheet_names = WorkbookReader.get_ambiguous_sheet_names(sheet_names, existing_models_migrating)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            warn(msg, MigrateWarning)

        # use the existing_file sheet names to establish the order of existing models
        model_order = [None]*len(sheet_names)
        ambiguous_models = []
        for existing_model in existing_models_migrating:
            try:
                sheet_name = WorkbookReader.get_model_sheet_name(sheet_names, existing_model)
                if sheet_name is not None:
                    model_order[sheet_names.index(sheet_name)] = existing_model
            except ValueError:
                ambiguous_models.append(existing_model)
        model_order = [element for element in model_order if element is not None]

        # append models with ambiguous sheets
        model_order.extend(ambiguous_models)

        return model_order

    def _migrate_model_order(self, model_order):
        """ Migrate the sequence of models from the existing order to a migrated order

        Map the order of existing models to an order for migrated models. The migrated order can be
        used to sequence worksheets or files in migrated file(s).

        Args:
            model_order (:obj:`list` of `obj_model.core.ModelMeta`:): order of existing models

        Returns:
            :obj:`list` of `obj_model.core.ModelMeta`: migrated models in the same order as
                the corresponding existing models, followed by migrated models sorted by name
        """

        model_type_map = {}
        for existing_model, migrated_model in self.models_map.items():
            model_type_map[self.existing_defs[existing_model]] = self.migrated_defs[migrated_model]

        migrated_model_order = []
        for existing_model in model_order:
            try:
                migrated_model_order.append(model_type_map[existing_model])
            except KeyError:
                raise MigratorError("model '{}' not found in the model map".format(
                    existing_model.__name__))

        # append newly created models
        migrated_model_names = [migrated_model_name
            for migrated_model_name in set(self.migrated_defs).difference(self.models_map.values())]
        migrated_models = [self.migrated_defs[model_name] for model_name in sorted(migrated_model_names)]
        migrated_model_order.extend(migrated_models)

        return migrated_model_order

    @staticmethod
    def _get_models_with_worksheets(models):
        """ Select subset of `models` that are stored in a worksheet or file

        Args:
            models (:obj:`dict` of `obj_model.core.ModelMeta`): model classes keyed by name

        Returns:
            :obj:`str`: name of migrated file
        """
        return [model for model in models.values() if model.Meta.tabular_orientation != TabularOrientation.inline]

    def read_existing_model(self, existing_file):
        """ Read models from existing file

        Does not perform validation -- data in existing model file must be already validated with the existing schema.

        Args:
            existing_file (:obj:`str`): pathname of file to migrate

        Returns:
            :obj:`list` of `obj_model.Model`: the models in `existing_file`
        """
        # todo: simplify these 2 commands into 1
        obj_model_reader = obj_model.io.Reader.get_reader(existing_file)()
        # ignore_sheet_order because models obtained by inspect.getmembers() are returned in name order
        # data in model files must be already validated with the existing schema
        existing_models = obj_model_reader.run(existing_file, models=self._get_models_with_worksheets(self.existing_defs),
            ignore_attribute_order=True, ignore_sheet_order=True, include_all_attributes=False, validate=False)
        models_read = []
        for models in existing_models.values():
            models_read.extend(models)
        return models_read

    def migrate(self, existing_models):
        """ Migrate existing model instances to migrated schema

        Args:
            existing_models (:obj:`list` of `obj_model.Model`:) the models being migrated

        Returns:
            :obj:`list` of `obj_model.Model`: the migrated models
        """
        all_models = self._deep_migrate(existing_models)
        self._connect_models(all_models)
        migrated_models = [migrated_model for _, migrated_model in all_models]
        return migrated_models

    @staticmethod
    def path_of_migrated_file(existing_file, migrate_suffix=None, migrate_in_place=False):
        """ Determine the pathname of the migrated file

        Args:
            existing_file (:obj:`str`): pathname of file being migrated
            migrate_suffix (:obj:`str`, optional): suffix of automatically created migrated filename;
                default is `Migrator.MIGRATE_SUFFIX`
            migrate_in_place (:obj:`bool`, optional): if set, migrated file is `existing_file`, which
                will be overwritten

        Returns:
            :obj:`str`: name of migrated file
        """
        if migrate_in_place:
            return existing_file
        root, ext = os.path.splitext(existing_file)
        if migrate_suffix is None:
            migrate_suffix = Migrator.MIGRATE_SUFFIX
        migrated_file = os.path.join(os.path.dirname(existing_file),
            os.path.basename(root) + migrate_suffix + ext)
        return migrated_file

    def write_migrated_file(self, migrated_models, model_order, existing_file, migrated_file=None,
        migrate_suffix=None, migrate_in_place=False):
        """ Write migrated models to an external representation

        Does not perform validation -- validation must be performed independently.

        Args:
            migrated_models (:obj:`list` of `obj_model.Model`:) the migrated models
            model_order (:obj:`list` of `obj_model.core.ModelMeta`:) migrated models in the order
                they should appear in a workbook
            existing_file (:obj:`str`): pathname of file that is being migrated
            migrated_file (:obj:`str`, optional): pathname of migrated file; if not provided,
                save migrated file with migrated suffix in same directory as source file
            migrate_suffix (:obj:`str`, optional): suffix of automatically created migrated filename;
                default is `Migrator.MIGRATE_SUFFIX`
            migrate_in_place (:obj:`bool`, optional): if set, overwrite `existing_file` with the
                migrated file and ignore `migrated_file` and `migrate_suffix`

        Returns:
            :obj:`str`: name of migrated file

        Raises:
            :obj:`MigratorError`: if migrate_in_place is False and writing the migrated file would
                overwrite an existing file
        """
        if not migrated_file:
            migrated_file = self.path_of_migrated_file(existing_file,
                migrate_suffix=migrate_suffix, migrate_in_place=migrate_in_place)

        if not migrate_in_place and os.path.exists(migrated_file):
            raise MigratorError("migrated file '{}' already exists".format(migrated_file))

        # write migrated models to disk
        obj_model_writer = obj_model.io.Writer.get_writer(existing_file)()
        obj_model_writer.run(migrated_file, migrated_models, models=model_order, validate=False)
        return migrated_file

    def full_migrate(self, existing_file, migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        """ Migrate data from an existing file to a migrated file

        Args:
            existing_file (:obj:`str`): pathname of file to migrate
            migrated_file (:obj:`str`, optional): pathname of migrated file; if not provided,
                save migrated file with migrated suffix in same directory as existing file
            migrate_suffix (:obj:`str`, optional): suffix of automatically created migrated filename;
                default is `Migrator.MIGRATE_SUFFIX`
            migrate_in_place (:obj:`bool`, optional): if set, overwrite `existing_file` with the
                migrated file and ignore `migrated_file` and `migrate_suffix`

        Returns:
            :obj:`str`: name of migrated file

        Raises:
            :obj:`MigratorError`: if migrate_in_place is False and writing the migrated file would
                overwrite an existing file
        """
        existing_models = self.read_existing_model(existing_file)
        # execute PREPARE_EXISTING_MODELS transformations
        if self.transformations and self.PREPARE_EXISTING_MODELS in self.transformations:
            self.transformations[self.PREPARE_EXISTING_MODELS](self, existing_models)
        for count_uninitialized_attrs in self._check_models(existing_models):
            warn(count_uninitialized_attrs, MigrateWarning)
        migrated_models = self.migrate(existing_models)
        # execute MODIFY_MIGRATED_MODELS transformations
        if self.transformations and self.MODIFY_MIGRATED_MODELS in self.transformations:
            self.transformations[self.MODIFY_MIGRATED_MODELS](self, migrated_models)
        # get sequence of migrated models in workbook of existing file
        existing_model_order = self._get_existing_model_order(existing_file)
        migrated_model_order = self._migrate_model_order(existing_model_order)
        migrated_file = self.write_migrated_file(migrated_models, migrated_model_order, existing_file,
            migrated_file=migrated_file, migrate_suffix=migrate_suffix, migrate_in_place=migrate_in_place)
        return migrated_file

    def _check_model(self, existing_model, existing_model_def):
        """ Check a model instance against its definition

        Args:
            existing_model (:obj:`obj_model.Model`): the existing model
            existing_model_def (:obj:`obj_model.core.ModelMeta`): type of the existing model

        Returns:
            :obj:`list`: uninitialized attributes in `existing_model`
        """
        uninitialized_attrs = []

        # are attributes in existing_model_def missing or uninitialized in existing_model
        for attr_name, attr in existing_model_def.Meta.attributes.items():
            if not hasattr(existing_model, attr_name) or \
                getattr(existing_model, attr_name) is attr.get_default_cleaned_value():
                uninitialized_attrs.append("instance(s) of existing model '{}' lack(s) '{}' non-default value".format(
                    existing_model_def.__name__, attr_name))

        return uninitialized_attrs

    def _check_models(self, existing_models):
        """ Check existing model instances against their definitions

        Args:
            existing_models (:obj:`list` of `obj_model.Model`:) the models being migrated

        Returns:
            :obj:`list`: counts of uninitialized attributes in `existing_models`
        """
        existing_models_dict = dict_by_class(existing_models)
        uninitialized_attrs = []
        for existing_model_def, existing_models in existing_models_dict.items():
            for existing_model in existing_models:
                uninitialized_attrs.extend(self._check_model(existing_model, existing_model_def))
        counts_uninitialized_attrs = []
        for uninitialized_attr, count in det_count_elements(uninitialized_attrs):
            counts_uninitialized_attrs.append("{} {}".format(count, uninitialized_attr))
        return counts_uninitialized_attrs

    def _migrate_model(self, existing_model, existing_model_def, migrated_model_def):
        """ Migrate a model instance's non-related attributes

        Args:
            existing_model (:obj:`obj_model.Model`): the existing model
            existing_model_def (:obj:`obj_model.core.ModelMeta`): type of the existing model
            migrated_model_def (:obj:`obj_model.core.ModelMeta`): type of the migrated model

        Returns:
            :obj:`obj_model.Model`: a `migrated_model_def` instance migrated from `existing_model`
        """
        migrated_model = migrated_model_def()

        # copy non-Related attributes from existing_model to migrated_model
        for attr in existing_model_def.Meta.attributes.values():
            val = getattr(existing_model, attr.name)

            # skip attributes that do not get migrated to migrated_model_def
            _, migrated_attr = self._get_mapped_attribute(existing_model_def, attr)
            if migrated_attr is None:
                continue

            if not isinstance(attr, obj_model.RelatedAttribute):
                if val is None:
                    copy_val = val
                elif isinstance(val, (string_types, bool, integer_types, float, Enum, )):
                    copy_val = val
                elif isinstance(attr, obj_model.ontology.OntologyAttribute):
                    # pronto does not properly implement deepcopy
                    # temporarily share refs to OntologyAttribute between existing and migrated models
                    copy_val = val
                else:
                    copy_val = copy.deepcopy(val)

                setattr(migrated_model, migrated_attr, copy_val)

        # save a reference to migrated_model in existing_model, which is used by _connect_models()
        setattr(existing_model, self._migrated_copy_attr_name, migrated_model)
        return migrated_model

    def _migrate_expression(self, existing_analyzed_expr):
        """ Migrate a model instance's `ParsedExpression.expression`

        The ParsedExpression syntax supports model type names in a ModelName.model_id notation.
        If a model type name changes then these must be migrated.

        Args:
            existing_analyzed_expr (:obj:`ParsedExpression`): an existing model's `ParsedExpression`

        Returns:
            :obj:`str`: a migrated `existing_analyzed_expr.expression`
        """
        types_of_referenced_models = existing_analyzed_expr.related_objects.keys()
        changed_model_types = {}
        for existing_model_type in existing_analyzed_expr.related_objects.keys():
            existing_model_type_name = existing_model_type.__name__
            if existing_model_type_name != self.models_map[existing_model_type_name]:
                changed_model_types[existing_model_type_name] = self.models_map[existing_model_type_name]

        if not changed_model_types:
            # migration doesn't change data; if model type names didn't change then expression hasn't either
            return existing_analyzed_expr.expression
        else:
            # rename changed model type names used in ModelType.id notation
            wc_token_strings = []
            for wc_token in existing_analyzed_expr._obj_model_tokens:
                wc_token_string = wc_token.token_string
                if wc_token.code == ObjModelTokenCodes.obj_id and \
                    wc_token.model_type.__name__ in changed_model_types and \
                    wc_token_string.startswith(wc_token.model_type.__name__ + '.'):

                    # disambiguated referenced model
                    migrated_model_type_name = changed_model_types[wc_token.model_type.__name__]
                    migrated_wc_token_string = wc_token_string.replace(wc_token.model_type.__name__ + '.',
                        migrated_model_type_name + '.')
                    wc_token_strings.append(migrated_wc_token_string)
                else:
                    wc_token_strings.append(wc_token_string)

            migrated_expr_wo_spaces = ''.join(wc_token_strings)
            return existing_analyzed_expr.recreate_whitespace(migrated_expr_wo_spaces)

    def _migrate_analyzed_expr(self, existing_model, migrated_model, migrated_models):
        """ Run the migration of a model instance's `ParsedExpression` attribute, if it has one

        This must be done after all migrated models have been created. The migrated `ParsedExpression`
        is assigned to the appropriate attribute in `migrated_model`.

        Args:
            existing_model (:obj:`obj_model.Model`): the existing model
            migrated_model (:obj:`obj_model.Model`): the corresponding migrated model
            migrated_models (:obj:`dict`): dict of Models; maps migrated model type to a dict mapping
                migrated model ids to migrated model instances

        Raises:
            :obj:`MigratorError`: if the `ParsedExpression` in `existing_model` cannot be migrated
        """
        if hasattr(existing_model, self.PARSED_EXPR):
            existing_analyzed_expr = getattr(existing_model, self.PARSED_EXPR)
            migrated_attribute = self.PARSED_EXPR
            migrated_expression = self._migrate_expression(existing_analyzed_expr)
            migrated_given_model_types = []
            for existing_model_type in existing_analyzed_expr.related_objects.keys():
                migrated_given_model_types.append(self.migrated_defs[self.models_map[existing_model_type.__name__]])
            parsed_expr = ParsedExpression(migrated_model.__class__, migrated_attribute, migrated_expression, migrated_models)
            _, _, errors = parsed_expr.tokenize()
            if errors:
                raise MigratorError('\n'.join(errors))
            setattr(migrated_model, self.PARSED_EXPR, parsed_expr)

    def _migrate_all_analyzed_exprs(self, all_models):
        """ Migrate all model instances' `ParsedExpression`s

        This must be done after all migrated models have been created.

        Args:
            all_models (:obj:`list` of `tuple`): pairs of corresponding existing and migrated model instances

        Raises:
            :obj:`MigratorError`: if multiple instances of a model type have the same id
        """
        errors = []
        migrated_models = {}
        for _, migrated_model in all_models:
            if migrated_model.__class__ not in migrated_models:
                migrated_models[migrated_model.__class__] = {}
            # ignore models that do not have an 'id' attribute
            if hasattr(migrated_model, 'id'):
                id = migrated_model.id
                if id in migrated_models[migrated_model.__class__]:
                    errors.append("model type '{}' has duplicated id: '{}' ".format(
                        migrated_model.__class__.__name__, id))
                migrated_models[migrated_model.__class__][id] = migrated_model
        if errors:
            raise MigratorError('\n'.join(errors))

        for existing_model, migrated_model in all_models:
            self._migrate_analyzed_expr(existing_model, migrated_model, migrated_models)

    def _deep_migrate(self, existing_models):
        """ Migrate all model instances from existing to migrated model definitions

        Supports:

        * delete attributes from existing schema
        * add attributes in migrated schema
        * add model definitions in migrated schema
        * models with expressions

        Assumes that otherwise the schemas are identical

        Args:
            existing_models (:obj:`list` of `obj_model.Model`): the existing models

        Returns:
            :obj:`list`: list of (existing model, corresponding migrated model) pairs
        """
        existing_schema = self.existing_defs
        migrated_schema = self.migrated_defs

        all_models = []
        for existing_model in existing_models:
            existing_class_name = existing_model.__class__.__name__

            # do not migrate model instancess whose classes are not in the migrated schema
            if existing_class_name in self.deleted_models:
                continue

            migrated_class_name = self.models_map[existing_class_name]
            migrated_model = self._migrate_model(existing_model, existing_schema[existing_class_name],
                migrated_schema[migrated_class_name])
            all_models.append((existing_model, migrated_model))
        self._migrate_all_analyzed_exprs(all_models)
        return all_models

    def _connect_models(self, all_models):
        """ Connect migrated model instances

        Migrate `obj_model.RelatedAttribute` connections among existing models to migrated models

        Args:
            all_models (:obj:`list` of `tuple`): pairs of corresponding existing and migrated model instances
        """
        for existing_model, migrated_model in all_models:
            existing_model_cls = existing_model.__class__
            for attr_name, attr in existing_model_cls.Meta.attributes.items():

                # skip attributes that are not in migrated_model_def
                _, migrated_attr = self._get_mapped_attribute(existing_model_cls, attr)
                if migrated_attr is None:
                    continue

                if isinstance(attr, obj_model.RelatedAttribute):
                    val = getattr(existing_model, attr_name)
                    if val is None:
                        migrated_val = val
                    elif isinstance(val, obj_model.core.Model):
                        migrated_val = getattr(val, self._migrated_copy_attr_name)
                    elif isinstance(val, (set, list, tuple)):
                        migrated_val = []
                        for model in val:
                            migrated_val.append(getattr(model, self._migrated_copy_attr_name))
                    else:
                        # unreachable due to other error checking
                        raise MigratorError('Invalid related attribute value')  # pragma: no cover

                    setattr(migrated_model, migrated_attr, migrated_val)

        for existing_model, migrated_model in all_models:
            # delete the reference to migrated_model in existing_model
            delattr(existing_model, self._migrated_copy_attr_name)

    @staticmethod
    def generate_wc_lang_migrator(**kwargs):
        """ Generate a `Migrator` for a WC-Lang (`wc_lang`) model

        WC-Lang model files must contain exactly one `Model` instance, and as a convenience for users,
        they allow uninitialized `model` attributes which reference the `Model` instance. Like
        `wc_lang.io.Reader`, the `Migrator` generated here initializes these attributes.
        This ensures that model files written by the `Migrator` contain initialized `Model` references,
        and enables round-trip migrations of WC-Lang model files.

        Args:
            kwargs (:obj:`dict`) arguments for `Migrator()`, except `transformations`

        Returns:
            :obj:`Migrator`: a new `Migrator`, with a transformation that initializes `model`
                attributes which reference the `Model` instance

        Raises:
            :obj:`MigratorError`: if `kwargs` contains `transformations`
        """
        if 'transformations' in kwargs:
            raise MigratorError("'transformations' entry not allowed in kwargs:\n{}".format(pformat(kwargs)))
        def prepare_existing_wc_lang_models(migrator, existing_models):
            # reproduce the 'add implicit relationships to `Model`' code in wc_lang/io.py
            existing_models_dict = dict_by_class(existing_models)
            model_cls = migrator.existing_defs['Model']
            num_model_instances = 0
            if model_cls in existing_models_dict:
                num_model_instances = len(existing_models_dict[model_cls])
            if num_model_instances != 1:
                raise MigratorError("existing models must have 1 Model instance, but {} are present".format(
                    num_model_instances))
            root_model = existing_models_dict[model_cls][0]
            for cls, cls_objects in existing_models_dict.items():
                for attr in cls.Meta.attributes.values():
                    if isinstance(attr, obj_model.RelatedAttribute) and attr.related_class == model_cls:
                        for cls_obj in cls_objects:
                            setattr(cls_obj, attr.name, root_model)

        transformations = {Migrator.PREPARE_EXISTING_MODELS: prepare_existing_wc_lang_models}
        return Migrator(**kwargs, transformations=transformations)

    def run(self, files):
        """ Migrate some files

        Args:
            files (:obj:`list`): names of model files to migrate
        """
        migrated_files = []
        for file in files:
            migrated_files.append(self.full_migrate(normalize_filename(file)))
        return migrated_files

    def __str__(self):
        """ Get str representation

        Returns:
            :obj:`str`: string representation of a `Migrator`; collections attributes are rendered
                by `pformat`
        """
        rv = []
        for attr in self.SCALAR_ATTRS:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                rv.append("{}: {}".format(attr, getattr(self, attr)))
        for attr in self.COLLECTIONS_ATTRS:
            if hasattr(self, attr):
                rv.append("{}:\n{}".format(attr, pformat(getattr(self, attr))))
        return '\n'.join(rv)


class MigrationSpec(object):
    """ Specification of a sequence of migrations for a list of existing files

    Attributes:
        _REQUIRED_ATTRS (:obj:`list` of :obj:`str`): required attributes in a `MigrationSpec`
        _CHANGES_LISTS (:obj:`list` of :obj:`str`): lists of changes in a migration
        _ALLOWED_ATTRS (:obj:`list` of :obj:`str`): attributes allowed in a `MigrationSpec`
        name (:obj:`str`): name for this `MigrationSpec`
        migrator (:obj:`str`): the name of a Migrator to use for migrations, which must be a key in
            `self.MIGRATOR_CREATOR_MAP`; default = `standard_migrator`, which maps to `Migrator`
        existing_files (:obj:`list`: of :obj:`str`, optional): existing files to migrate
        schema_files (:obj:`list` of :obj:`str`, optional): list of Python files containing model
            definitions for each state in a sequence of migrations
        seq_of_renamed_models (:obj:`list` of :obj:`list`, optional): list of renamed models for use
            by a `Migrator` for each migration in a sequence of migrations
        seq_of_renamed_attributes (:obj:`list` of :obj:`list`, optional): list of renamed attributes
            for use by a `Migrator` for each migration in a sequence of migrations
        seq_of_transformations (:obj:`list` of :obj:`dict`, optional): list of transformations
            for use by a `Migrator` for each migration in a sequence of migrations
        migrated_files (:obj:`list`: of :obj:`str`, optional): migration destination files in 1-to-1
            correspondence with `existing_files`; if not provided, migrated files use a suffix or
            are migrated in place
        migrate_suffix (:obj:`str`, optional): suffix added to destination file name, before the file type suffix
        migrate_in_place (:obj:`bool`, optional): whether to migrate in place
        migrations_config_file (:obj:`str`, optional): if created from a configuration file, the file's
            path
        _prepared (:obj:`bool`, optional): whether this `MigrationSpec` has been prepared
    """

    # map migrator names to callables that create `Migrator`s
    DEFAULT_MIGRATOR = 'standard_migrator'
    MIGRATOR_CREATOR_MAP = {DEFAULT_MIGRATOR: Migrator, 'wc_lang': Migrator.generate_wc_lang_migrator}

    _REQUIRED_ATTRS = ['name', 'migrator', 'existing_files', 'schema_files']
    _CHANGES_LISTS = ['seq_of_renamed_models', 'seq_of_renamed_attributes', 'seq_of_transformations']
    _ALLOWED_ATTRS = _REQUIRED_ATTRS + _CHANGES_LISTS + ['migrated_files', 'migrate_suffix',
        'migrate_in_place', 'migrations_config_file', '_prepared', 'DEFAULT_MIGRATOR',
        'MIGRATOR_CREATOR_MAP']

    def __init__(self, name, migrator=DEFAULT_MIGRATOR, existing_files=None, schema_files=None,
        seq_of_renamed_models=None, seq_of_renamed_attributes=None, seq_of_transformations=None,
        migrated_files=None, migrate_suffix=None, migrate_in_place=False, migrations_config_file=None):
        self.name = name
        self.migrator = migrator
        self.existing_files = existing_files
        self.schema_files = schema_files
        self.seq_of_renamed_models = seq_of_renamed_models
        self.seq_of_renamed_attributes = seq_of_renamed_attributes
        self.seq_of_transformations = seq_of_transformations
        self.migrated_files = migrated_files
        self.migrate_suffix = migrate_suffix
        self.migrate_in_place = migrate_in_place
        self.migrations_config_file = migrations_config_file
        self._prepared = False

    def prepare(self):
        """ Validate and standardize this `MigrationSpec`

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read, or the migration specifications in
                `migrations_config_file` are not valid
        """
        migration_errors = self.validate()
        if migration_errors:
            raise MigratorError('\n'.join(migration_errors))
        self.standardize()
        self._prepared = True

    def is_prepared(self):
        """ Check that this `MigrationSpec` has been prepared

        Raises:
            :obj:`MigratorError`: if this `MigrationSpec` has not been prepared
        """
        if not self._prepared:
            raise MigratorError("MigrationSpec '{}' is not prepared".format(self.name))

    @classmethod
    def load(cls, migrations_config_file):
        """ Create a list of validated and standardized `MigrationSpec`s from a migrations configuration file

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`dict` of :obj:`MigrationSpec`: migration specifications

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read, or the migration specifications in
                `migrations_config_file` are not valid
        """
        migration_specs = cls.get_migrations_config(migrations_config_file)

        migration_errors = []
        for migration_spec_obj in migration_specs.values():
            migration_errors.extend(migration_spec_obj.validate())
        if migration_errors:
            raise MigratorError('\n'.join(migration_errors))
        for migration_spec_obj in migration_specs.values():
            migration_spec_obj.standardize()
            migration_spec_obj._prepared = True

        return migration_specs

    @staticmethod
    def get_migrations_config(migrations_config_file):
        """ Create a list of `MigrationSpec`s from a migrations configuration file

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`dict` of :obj:`MigrationSpec`: migration specifications

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read
        """
        try:
            fd = open(migrations_config_file, 'r')
        except FileNotFoundError as e:
            raise MigratorError("could not read migration config file: '{}'".format(migrations_config_file))

        try:
            migrations_config = yaml.load(fd, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            raise MigratorError("could not parse YAML migration config file: '{}':\n{}".format(
                migrations_config_file, e))

        # parse the migrations config
        migration_specs = {}
        for migration_name, migration_spec in migrations_config.items():
            migration_spec_obj = MigrationSpec(migration_name, migrations_config_file=migrations_config_file)
            for param, value in migration_spec.items():
                setattr(migration_spec_obj, param, value)
            migration_specs[migration_name] = migration_spec_obj

        return migration_specs

    def validate(self):
        """ Validate the attributes of a migration specification

        Returns:
            :obj:`list` of :obj:`str`: list of errors found
        """
        errors = []
        # check all attributes of self that aren't classes, methods, functions, or private
        members = inspect.getmembers(self, lambda a:
            not(inspect.isclass(a) or inspect.ismethod(a) or inspect.isfunction(a)))
        members = [attr for attr, value in members if not attr.startswith('_')]

        extra_attrs = set(members).difference(self._ALLOWED_ATTRS)
        if extra_attrs:
            errors.append("disallowed attribute(s) found: {}".format(extra_attrs))

        for required_attr in self._REQUIRED_ATTRS:
            if not hasattr(self, required_attr) or getattr(self, required_attr) is None:
                errors.append("missing required attribute '{}'".format(required_attr))
        if errors:
            return errors

        if len(self.schema_files) < 2:
            return ["a migration spec must contain at least 2 model definitions, but it has only {}".format(
                len(self.schema_files))]

        for changes_list in self._CHANGES_LISTS:
            if getattr(self, changes_list) is not None:
                if len(getattr(self, changes_list)) != len(self.schema_files) - 1:
                    errors.append("{} must have 1 mapping for each of the {} migration(s) specified, "
                        "but it has {}".format(changes_list,  len(self.schema_files) - 1,
                        len(getattr(self, changes_list))))

        if self.seq_of_renamed_models:
            required_structure = "seq_of_renamed_models must be None, or a list of lists of pairs of strings"
            try:
                for renaming in self.seq_of_renamed_models:
                    if renaming is not None:
                        for pair in renaming:
                            if len(pair) != 2 or not isinstance(pair[0], str) or not isinstance(pair[1], str):
                                errors.append(required_structure)
            except TypeError as e:
                errors.append(required_structure + ", but examining it raises a '{}' error".format(str(e)))

        if self.seq_of_renamed_attributes:
            required_structure = ( "seq_of_renamed_attributes must be None, or a list of lists of pairs "
                "of pairs of strings")
            try:
                for renamings in self.seq_of_renamed_attributes:
                    if renamings is not None:
                        for attribute_renaming in renamings:
                            for attr_spec in attribute_renaming:
                                if len(attr_spec) != 2 or not isinstance(attr_spec[0], str) or \
                                    not isinstance(attr_spec[1], str):
                                    errors.append(required_structure)
            except TypeError as e:
                errors.append(required_structure + ", but examining it raises a '{}' error".format(str(e)))

        if len(self.existing_files) < 1:
            errors.append("at least one existing file must be specified")

        # ensure that migrated_files is empty or specifies same count as existing_files
        if self.migrated_files is not None and len(self.migrated_files) != len(self.existing_files):
            errors.append("existing_files and migrated_files must provide 1-to-1 corresponding files, "
                "but they have {} and {} entries, respectively".format(len(self.existing_files),
                len(self.migrated_files)))

        # ensure a valid value of 'migrator'
        if not hasattr(self, 'migrator') or self.migrator not in self.MIGRATOR_CREATOR_MAP:
            errors.append("'migrator' must be an element of {}".format(
                set(self.MIGRATOR_CREATOR_MAP.keys())))

        return errors

    @staticmethod
    def _normalize_filenames(filenames, absolute_file=None):
        """ Normalize filenames relative to directory containing existing file

        Args:
            filenames (:obj:`list` of :obj:`str`): list of filenames
            absolute_file (:obj:`str`, optional): file whose directory contains files in `filenames`

        Returns:
            :obj:`list` of :obj:`str`: absolute paths for files in `filenames`
        """
        dir = None
        if absolute_file:
            dir = os.path.dirname(absolute_file)
        return [normalize_filename(filename, dir=dir) for filename in filenames]

    def standardize(self):
        """ Standardize the attributes of a `MigrationSpec`

        In particular, standardize a `MigrationSpec` read from a YAML config file
        """
        # convert [model, attr] pairs in seq_of_renamed_attributes into tuples; needed for hashing
        if self.seq_of_renamed_attributes:
            migrated_renamed_attributes = []
            for renamed_attrs_in_a_migration in self.seq_of_renamed_attributes:
                if renamed_attrs_in_a_migration == []:
                    migrated_renamed_attributes.append(None)
                    continue
                a_migration_renaming = []
                for existing, migrated in renamed_attrs_in_a_migration:
                    a_migration_renaming.append((tuple(existing), tuple(migrated)))
                migrated_renamed_attributes.append(a_migration_renaming)
            self.seq_of_renamed_attributes = migrated_renamed_attributes

        # if a changes_list isn't provided, replace it with a list of Nones indicating no changes
        empty_per_migration_list = [None]*(len(self.schema_files) - 1)
        for changes_list in self._CHANGES_LISTS:
            if getattr(self, changes_list) is None:
                setattr(self, changes_list, empty_per_migration_list)

        # normalize filenames
        if self.migrations_config_file:
            self.existing_files = self._normalize_filenames(self.existing_files,
                absolute_file=self.migrations_config_file)
            self.schema_files = self._normalize_filenames(self.schema_files,
                absolute_file=self.migrations_config_file)
            if self.migrated_files:
                self.migrated_files = self._normalize_filenames(self.migrated_files,
                    absolute_file=self.migrations_config_file)

    def get_migrator(self):
        """ Obtain callable that creates `Migrator`s for this `MigrationSpec`

        Returns:
            :obj:`callable`: a callable that creates `Migrator`s for this `MigrationSpec`
        """
        return self.MIGRATOR_CREATOR_MAP[self.migrator]

    def expected_migrated_files(self):
        """ Provide names of migrated files that migration of this `MigrationSpec` would produce

        Returns:
            :obj:`list` of :obj:`str`: the names of the migrated files that a successful migration of this
                `MigrationSpec` will produce
        """
        if self.migrated_files:
            return self.migrated_files
        migrated_files = []
        for existing_file in self.existing_files:
            migrated_files.append(
                Migrator.path_of_migrated_file(existing_file, migrate_suffix=self.migrate_suffix,
                    migrate_in_place=self.migrate_in_place))
        return migrated_files

    def __str__(self):
        """ Get str representation

        Returns:
            :obj:`str`: string representation of all allowed attributes in a `MigrationSpec`
        """
        rv = []
        for attr in self._ALLOWED_ATTRS:
            if attr in self._CHANGES_LISTS:
                rv.append("{}:\n{}".format(attr, pformat(getattr(self, attr))))
            else:
                rv.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(rv)


class MigrationController(object):
    """ Manage migrations

    Manage migrations on several dimensions:
    * Migrate a single model file through a sequence of schemas
    * Perform migrations parameterized by a configuration file
    """

    @staticmethod
    def migrate_over_schema_sequence(migration_spec):
        """ Migrate some model files over a sequence of schemas

        Args:
            migration_spec (:obj:`MigrationSpec`): a migration specification

        Returns:
            :obj:`tuple` of :obj:`list`, :obj:`list`: for each migration, its sequence of models and
                its migrated filename

        Raises:
            :obj:`MigratorError`: if `schema_files`, `renamed_models`, and `seq_of_renamed_attributes`
                are not consistent with each other;
        """
        md = migration_spec
        md.is_prepared()

        # iterate over existing_files & migrated_files
        migrated_files = md.migrated_files if md.migrated_files else [None] * len(md.existing_files)
        all_models, all_migrated_files = [], []
        for existing_file, migrated_file in zip(md.existing_files, migrated_files):
            num_migrations = len(md.schema_files) - 1
            # since 0 < num_migrations this loop always executes and branch coverage reports that
            # the 'for' line doesn't jump to return; this cannot be annotated with 'pragma: no cover'
            for i in range(num_migrations):
                # create Migrator for each pair of schemas
                migrator_creator = migration_spec.get_migrator()
                migrator = migrator_creator(existing_defs_file=md.schema_files[i],
                    migrated_defs_file=md.schema_files[i+1], renamed_models=md.seq_of_renamed_models[i],
                    renamed_attributes=md.seq_of_renamed_attributes[i])
                migrator.prepare()
                # the 1st iteration inits `models` from the existing file; iteration n+1 uses `models` set in n
                if i == 0:
                    models = migrator.read_existing_model(existing_file)
                    all_models.append(models)
                    model_order = migrator._get_existing_model_order(existing_file)
                for count_uninitialized_attrs in migrator._check_models(models):
                    warn(count_uninitialized_attrs, MigrateWarning)
                # migrate in memory until the last migration
                models = migrator.migrate(models)
                all_models.append(models)
                model_order = migrator._migrate_model_order(model_order)
                if i == num_migrations - 1:
                    # done migrating, write to file
                    actual_migrated_file = migrator.write_migrated_file(models, model_order, existing_file,
                        migrated_file=migrated_file, migrate_suffix=md.migrate_suffix,
                        migrate_in_place=md.migrate_in_place)
                    all_migrated_files.append(actual_migrated_file)

        return all_models, all_migrated_files

    @staticmethod
    def migrate_from_spec(migration_spec):
        """ Perform the migration specified in a `MigrationSpec`

        Args:
            migration_spec (:obj:`MigrationSpec`): a migration specification

        Returns:
            :obj:`list`: of :obj:`str`: migrated filenames
        """
        migration_spec.is_prepared()
        _, migrated_filenames = MigrationController.migrate_over_schema_sequence(migration_spec)
        return migrated_filenames

    @staticmethod
    def migrate_from_config(migrations_config_file):
        """ Perform the migrations specified in a config file

        Args:
            migrations_config_file (:obj:`str`): migrations specified in a YAML file

        Returns:
            :obj:`list` of :obj:`tuple`: list of (`MigrationSpec`, migrated filenames) pairs
        """
        migration_specs = MigrationSpec.load(migrations_config_file)
        results = []
        for migration_spec in migration_specs.values():
            results.append((migration_spec, MigrationController.migrate_from_spec(migration_spec)))
        return results


class SchemaChanges(object):
    """ Specification of the changes to a schema in a git commit

    Attributes:
        _CHANGES_FILE_ATTRS (:obj:`list` of :obj:`str`): required attributes in a schema changes file
        _ATTRIBUTES (:obj:`list` of :obj:`str`): attributes in a `SchemaChanges` instance
        git_repo (:obj:`GitRepo`): a git_repo that defines the data model of data being migrated
        schema_changes_file (:obj:`str`): the schema changes file
        commit_hash (:obj:`str`): hash from a schema changes file
        renamed_models (:obj:`list`, optional): list of renamed models in the commit
        renamed_attributes (:obj:`list`, optional): list of renamed attributes in the commit
        transformations_file (:obj:`str`, optional): the name of a Python file containing transformations
        transformations (:obj:`dict`, optional): the transformations for a migration to the schema,
            in a dictionary of callables
    """
    _CHANGES_FILE_ATTRS = ['commit_hash', 'renamed_models', 'renamed_attributes', 'transformations_file']

    _ATTRIBUTES = ['git_repo', 'transformations', 'schema_changes_file', 'commit_hash',
        'renamed_models', 'renamed_attributes', 'transformations_file']

    # template for the name of a schema changes file; the format placeholders are replaced
    # with the file's creation timestamp and the prefix of the commit's git hash, respectively
    _CHANGES_FILENAME_TEMPLATE = "schema_changes_{}_{}.yaml"
    _HASH_PREFIX_LEN = 7
    _SHA1_LEN = 40

    def __init__(self, git_repo=None, schema_changes_file=None, commit_hash=None, renamed_models=None,
        renamed_attributes=None, transformations_file=None):
        self.git_repo = git_repo
        self.schema_changes_file = schema_changes_file
        self.commit_hash = commit_hash
        self.renamed_models = renamed_models
        self.renamed_attributes = renamed_attributes
        self.transformations_file = transformations_file
        self.transformations = None

    def get_hash(self):
        """ Get the repo's current commit hash

        Returns:
            :obj:`str`: the hash
        """
        return self.git_repo.latest_hash()

    @staticmethod
    def hash_prefix(hash):
        """ Get a commit hash's prefix

        Args:
            hash (:obj:`str`): git commit hash

        Returns:
            :obj:`str`: hash's prefix
        """
        return hash[:SchemaChanges._HASH_PREFIX_LEN]

    @staticmethod
    def get_date_timestamp():
        """ Get a current date timestamp, with second resolution

        Returns:
            :obj:`str`: the timestamp
        """
        dt = datetime.datetime.now(tz=None)
        return dt.strftime("%Y-%m-%d-%H-%M-%S")

    @staticmethod
    def hash_prefix_from_sc_file(schema_changes_file):
        """ Get the hash prefix from a schema changes filename

        Args:
            schema_changes_file (:obj:`str`): the schema changes file

        Returns:
            :obj:`str`: the hash prefix in a schema changes filename
        """
        path = Path(schema_changes_file)
        return path.stem.split('_')[-1]

    @staticmethod
    def all_schema_changes_files(migrations_directory):
        """ Find all schema changes files in a git repo

        Args:
            migrations_directory (:obj:`str`): path to the migrations directory in a git repo

        Returns:
            :obj:`list`: of :obj:`str`: pathnames of the schema changes files

        Raises:
            :obj:`MigratorError`: if no schema changes files are found
        """
        # use glob to search
        pattern = SchemaChanges._CHANGES_FILENAME_TEMPLATE.format('*',  '*')
        files = list(Path(migrations_directory).glob(pattern))
        num_files = len(files)
        if not num_files:
            raise MigratorError("no schema changes files in '{}'".format(migrations_directory))
        return [str(file) for file in files]

    @staticmethod
    def all_schema_changes_with_commits(git_repo):
        """ Instantiate all schema changes in a git repo

        Obtain all validated schema change files

        Args:
            git_repo (:obj:`GitRepo`): an initialized git repo

        Returns:
            :obj:`tuple`: :obj:`list` of errors, :obj:`list` all validated schema change files
        """
        errors = []
        schema_changes_with_commits = []
        migrations_directory = git_repo.migrations_dir()
        for sc_file in SchemaChanges.all_schema_changes_files(migrations_directory):
            try:
                hash_prefix = SchemaChanges.hash_prefix_from_sc_file(sc_file)
                sc_dict = SchemaChanges.load(sc_file)
                commit_hash = sc_dict['commit_hash']
                if SchemaChanges.hash_prefix(commit_hash) != hash_prefix:
                    errors.append("hash prefix in schema changes filename '{}' inconsistent "
                        "with hash in file: '{}'".format(sc_file, sc_dict['commit_hash']))
                    continue

                # ensure that the hash corresponds to a commit
                try:
                    git_repo.get_commit(commit_hash)
                except MigratorError:
                    errors.append("the hash in '{}', which is '{}', isn't the hash of a commit".format(
                        sc_file, sc_dict['commit_hash']))
                    continue

                schema_changes_with_commits.append(SchemaChanges.generate_instance(sc_file))

            except MigratorError as e:
                errors.append(str(e))

        return errors, schema_changes_with_commits

    @staticmethod
    def find_file(git_repo, commit_hash):
        """ Find a schema changes file in a git repo

        Args:
            git_repo (:obj:`GitRepo`): an initialized git repo
            commit_hash (:obj:`str`): a git commit hash

        Returns:
            :obj:`str`: the pathname of the file found

        Raises:
            :obj:`MigratorError`: if a file with the hash cannot be found, or multiple files
                have the hash
        """
        # search with glob
        pattern = SchemaChanges._CHANGES_FILENAME_TEMPLATE.format('*',
            SchemaChanges.hash_prefix(commit_hash))
        migrations_directory = git_repo.migrations_dir()
        files = list(Path(migrations_directory).glob(pattern))
        num_files = len(files)
        if not num_files:
            raise MigratorError("no schema changes file in '{}' for hash {}".format(
                migrations_directory, commit_hash))
        if 1 < num_files:
            raise MigratorError("multiple schema changes files in '{}' for hash {}".format(
                migrations_directory, commit_hash))
        schema_changes_file = str(files[0])

        # ensure that hash in name and file are consistent
        sc_dict = SchemaChanges.load(schema_changes_file)
        if SchemaChanges.hash_prefix(sc_dict['commit_hash']) != SchemaChanges.hash_prefix(commit_hash):
            raise MigratorError("hash prefix in schema changes filename '{}' inconsistent "
                "with hash in file: '{}'".format(schema_changes_file, sc_dict['commit_hash']))

        # ensure that the hash corresponds to a commit
        try:
            git_repo.get_commit(commit_hash)
        except MigratorError:
            raise MigratorError("the hash in '{}', which is '{}', isn't the hash of a commit".format(
                schema_changes_file, sc_dict['commit_hash']))

        return schema_changes_file

    def generate_filename(self):
        """ Generate a filename for a template schema changes file

        The filename includes the current repo hash.

        Returns:
            :obj:`str`: the filename
        """
        return SchemaChanges._CHANGES_FILENAME_TEMPLATE.format(self.get_date_timestamp(),
            self.hash_prefix(self.get_hash()))

    def make_template(self, changes_file_dir=None, verbose=False):
        """ Make a template schema changes file

        The template includes the current repo hash and empty values for `SchemaChanges`
        attributes.

        Args:
            changes_file_dir (:obj:`str`, optional): directory for the schema changes file; default is
                migrations dir of current git repo
            verbose (:obj:`bool`): whether to print status and reminder; default=False

        Returns:
            :obj:`str`: pathname of the schema changes file that was written

        Raises:
            :obj:`MigratorError`: if the schema changes file already exists
        """
        filename = self.generate_filename()
        if not changes_file_dir and self.git_repo:
            changes_file_dir = self.git_repo.migrations_dir()
        pathname = os.path.join(changes_file_dir, filename)
        if os.path.exists(pathname):
            raise MigratorError("schema changes file '{}' already exists".format(pathname))

        with open(pathname, 'w') as file:
            file.write(u'# schema changes file\n')
            file.write(u"# stored in '{}'\n\n".format(filename))
            # generate YAML content
            template_data = dict(
                commit_hash=self.get_hash(),
                renamed_models=[],
                renamed_attributes=[],
                transformations_file=''
            )
            file.write(yaml.dump(template_data))

        # add the config file to the git repo, and print message encouraging a commit
        if self.git_repo:
            self.git_repo.repo.index.add([pathname])
        if verbose:
            print("created schema changes template '{}': edit it and run 'git commit'".format(pathname))
        return pathname

    def import_transformations(self):
        """ Import the transformation functions referenced in a schema changes file

        Returns:
            :obj:`dict`: the transformations for a migration to the schema, in a dictionary of callables

        Raises:
            :obj:`MigratorError`: if the transformations file cannot be imported,
                or it does not have a 'transformations' attribute,
                or 'transformations' isn't a dict of callables as specified by Migrator.SUPPORTED_TRANSFORMATIONS
        """
        if self.transformations_file:

            # import the transformations_file, if provided
            dir = os.path.dirname(self.schema_changes_file)
            transformations_schema_module = SchemaModule(self.transformations_file, dir=dir)
            transformations_module = transformations_schema_module.import_module_for_migration(validate=False)

            # extract the transformations
            if not hasattr(transformations_module, 'transformations'):
                raise MigratorError("'{}' does not have a 'transformations' attribute".format(
                    os.path.join(dir, self.transformations_file)))
            transformations = transformations_module.transformations

            # validate transformations
            errors = Migrator._validate_transformations(transformations)
            if errors:
                raise MigratorError('\n'.join(errors))
            return transformations

    @staticmethod
    def load(schema_changes_file):
        """ Load a schema changes file

        Args:
            schema_changes_file (:obj:`str`): path to the schema changes file

        Returns:
            :obj:`dict`: the data in the schema changes file

        Raises:
            :obj:`MigratorError`: if the schema changes file cannot be found,
                or is not proper YAML,
                or does not have the right format,
                or does not contain any changes
        """
        try:
            fd = open(schema_changes_file, 'r')
        except FileNotFoundError as e:
            raise MigratorError("could not read schema changes file: '{}'".format(
                schema_changes_file))
        try:
            schema_changes = yaml.load(fd, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            raise MigratorError("could not parse YAML schema changes file: '{}':\n{}".format(
                schema_changes_file, e))

        if not isinstance(schema_changes, dict) or \
            any([attr not in schema_changes for attr in SchemaChanges._CHANGES_FILE_ATTRS]):
                raise MigratorError("schema changes file '{}' must have a dict with these attributes:\n{}".format(
                    schema_changes_file, ', '.join(SchemaChanges._CHANGES_FILE_ATTRS)))

        if len(schema_changes['commit_hash']) != SchemaChanges._SHA1_LEN:
            raise MigratorError("schema changes file '{}' does not have a proper git hash".format(
                schema_changes_file))

        # report empty schema changes files (unmodified templates)
        if schema_changes['renamed_models'] == [] and \
            schema_changes['renamed_attributes'] == [] and \
            schema_changes['transformations_file'] == '':
                raise MigratorError("schema changes file '{}' is empty (an unmodified template)".format(
                    schema_changes_file))

        schema_changes['schema_changes_file'] = schema_changes_file
        return schema_changes

    @staticmethod
    def generate_instance(schema_changes_file):
        """ Generate a `SchemaChanges` instance from a schema changes file

        Args:
            schema_changes_file (:obj:`str`): path to the schema changes file

        Returns:
            :obj:`SchemaChanges`: the `SchemaChanges` instance
        """
        schema_changes_dict = SchemaChanges.load(schema_changes_file)
        return SchemaChanges(**schema_changes_dict)

    def __str__(self):
        """ Provide a string representation

        Returns:
            :obj:`str`: a string representation of this `SchemaChanges`
        """
        rv = []
        for attr in self._ATTRIBUTES:
            rv.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(rv)

    '''
    # todo: decide what to do about comparing GitRepos
    def __eq__(self, other):
        """ Compare two :obj:`SchemaChanges` objects

        Args:
            other (:obj:`Object`): other object

        Returns:
            :obj:`bool`: true if :obj:`SchemaChanges` objects are semantically equal
        """
        if other.__class__ is not self.__class__:
            return False

        for attr in self._ATTRIBUTES:
            if getattr(self, attr) != getattr(other, attr):
                return False

        return True
    '''


class GitRepo(object):
    """ Methods for processing a git repo and its commit history

    Attributes:
        repo_dir (:obj:`str`): the repo's root directory
        repo_url (:obj:`str`): the repo's url, if known
        repo (:obj:`git.Repo`): the repo
        commits_to_migrate (:obj:`list` of :obj:`git.objects.commit.Commit`): list of commits at which
            the schema needs to be migrated
        commit_DAG (:obj:`nx.classes.digraph.DiGraph`): `NetworkX` DAG of the repo's commit history
        git_hash_map (:obj:`dict`): map from all git hashes to their commits
        temp_dirs (:obj:`list` of :obj:`tempfile.TemporaryDirectory`): temp dirs that hold repo clones
    """
    # default repo name if name not known
    _NAME_UNKNOWN = 'name_unknown'

    def __init__(self, repo_location=None, search_parent_directories=False):
        """ Initialize a GitRepo

        Args:
            repo_location (:obj:`str`, optional): the location of the repo, either its root directory or URL
            search_parent_directories (:obj:`bool`, optional): `search_parent_directories` option to `git.Repo()`;
                if set, all parent directories will be searched for a valid repo as well; default=False

        Returns:
            :obj:`str`: root directory for the repo (which contains the .git directory)
        """
        self.commit_DAG = None
        self.git_hash_map = None
        self.temp_dirs = []
        self.repo = None
        self.repo_dir = None
        self.repo_url = None
        if repo_location:
            if os.path.isdir(repo_location):
                try:
                    self.repo = git.Repo(repo_location, search_parent_directories=search_parent_directories)
                except git.exc.GitError as e:
                    raise MigratorError("instantiating a git.Repo from directory '{}' failed".format(
                        repo_location))
                self.repo_dir = os.path.dirname(self.repo.git_dir)
            else:
                self.repo, self.repo_dir = self.clone_repo_from_url(repo_location)
                self.repo_url = repo_location
            self.commit_DAG = self.commits_as_graph()

    def get_temp_dir(self):
        """ Get a temporary directory, which will be deleted when this GitRepo is destroyed

        Returns:
            :obj:`str`: the pathname to a temporary directory
        """
        temp_dir = tempfile.TemporaryDirectory()
        self.temp_dirs.append(temp_dir)
        return temp_dir.name

    def clone_repo_from_url(self, url, directory=None):
        """ Clone a repo from an URL

        Args:
            url (:obj:`str`): URL for the repo
            directory (:obj:`str`, optional): directory to hold the repo; default is a temp dir

        Returns:
            :obj:`tuple`: (:obj:`git.Repo`, :obj:`str`): the repo cloned, and its root directory
                (which contains the .git directory)

        Raises:
            :obj:`MigratorError`: if repo cannot be cloned from `url`
        """
        if directory is None:
            directory = self.get_temp_dir()
        elif not os.path.isdir(directory):
            raise MigratorError("'{}' is not a directory".format(directory))
        try:
            repo = git.Repo.clone_from(url, directory)
        except Exception as e:
            raise MigratorError("repo cannot be cloned from '{}'\n{}".format(url, e))
        return repo, directory

    def migrations_dir(self):
        """ Get the repo's migrations directory

        Returns:
            :obj:`str`: the repo's migrations directory
        """
        return os.path.join(self.repo_dir, AutomatedMigration._MIGRATIONS_DIRECTORY)

    def fixtures_dir(self):
        """ Get the repo's fixtures directory

        Returns:
            :obj:`str`: the repo's fixtures directory
        """
        return os.path.join(self.repo_dir, 'tests', 'fixtures')

    def repo_name(self):
        """ Get the repo's name

        Returns:
            :obj:`str`: the repo's name
        """
        if self.repo_url:
            split_url = self.repo_url.split('/')
            return split_url[-1]
        elif self.repo_dir:
            return os.path.basename(self.repo_dir)
        # todo: get the name even if the repo is in tmp dir
        return self._NAME_UNKNOWN

    def latest_commit(self):
        """ Get the repo's latest commit

        Returns:
            :obj:`git.objects.commit.Commit`: the repo's latest commit
        """
        return self.repo.head.commit

    def latest_hash(self):
        """ Get the hash of the repo's latest commit

        Returns:
            :obj:`str`: the latest commit's SHA1 hash
        """
        return self.get_hash(self.latest_commit())

    def get_commit(self, commit_or_hash):
        """ Pass on a commit or convert a hash to its commit

        Args:
            commit_or_hash (:obj:`str` or :obj:`git.objects.commit.Commit`): the hash of a commit or a commit
                in the repo

        Returns:
            :obj:`git.objects.commit.Commit`: a commit

        Raises:
            :obj:`MigratorError`: if `commit_or_hash` is not a commit and cannot be converted into one
        """
        if isinstance(commit_or_hash, str):
            if commit_or_hash in self.git_hash_map:
                return self.git_hash_map[commit_or_hash]
        elif isinstance(commit_or_hash, git.objects.commit.Commit):
            return commit_or_hash
        raise MigratorError("commit_or_hash {} cannot be converted into a commit".format(commit_or_hash))

    def get_commits(self, commits_or_hashes):
        """ Get the commits with the given commits or hashes

        Args:
            commits_or_hashes (:obj:`list` of :obj:`str`): an iterator over commits or commit hashes

        Returns:
            :obj:`list` of :obj:`git.objects.commit.Commit`: list of the repo's commits with the
                commits or hashes in `commits_or_hashes`

        Raises:
            :obj:`MigratorError`: if any of the commits or hashes don't identify a commit in the repo
        """
        if not commits_or_hashes:
            return []
        commits = []
        bad_hashes = []
        for hash in commits_or_hashes:
            try:
                commits.append(self.get_commit(hash))
            except MigratorError:
                bad_hashes.append(hash)
        if bad_hashes:
            raise MigratorError("No commit found for {}".format(", or ".join(bad_hashes)))
        return commits

    def commits_as_graph(self):
        """ Make a DAG that represents the repo commit dependencies - edges point from dependent commit to parent commit

        The DAG contains all commits in the repo on which the latest commit depends. Also creates
        `git_hash_map`, a map from all git hashes to their commits.

        Returns:
            :obj:`nx.classes.digraph.DiGraph`: a DAG representing the repo commit history
        """
        self.git_hash_map = {}
        commit_graph = nx.DiGraph()
        latest = self.latest_commit()
        self.git_hash_map[self.get_hash(latest)] = latest
        commits_to_explore = {latest}
        commits_explored = set()
        while commits_to_explore:
            commit = commits_to_explore.pop()
            for parent in commit.parents:
                # edges point from dependent commit to parent commit
                commit_graph.add_edge(commit, parent)
                self.git_hash_map[self.get_hash(parent)] = parent
                if parent not in commits_explored:
                    commits_to_explore.add(parent)
            commits_explored.add(commit)
        return commit_graph

    @staticmethod
    def get_hash(commit):
        """ Get a commit's hash

        Args:
            commit (:obj:`git.objects.commit.Commit`): a commit

        Returns:
            :obj:`str`: the commit's SHA1 hash
        """
        return commit.hexsha

    def checkout_commit(self, commit_identifier):
        """ Checkout a commit for this repo

        Args:
            commit_identifier (:obj:`git.objects.commit.Commit` or :obj:`str`): a commit or a commit's hash

        Raises:
            :obj:`MigratorError`: if the commit cannot be checked out
        """
        if isinstance(commit_identifier, git.objects.commit.Commit):
            commit_hash = commit_identifier.hexsha
        elif isinstance(commit_identifier, str):   # pragma: can't tell coverage false branch cannot be covered
            commit_hash = commit_identifier
        # use git directly, as per https://gitpython.readthedocs.io/en/stable/tutorial.html#using-git-directly
        try:
            self.repo.git.checkout(commit_hash, detach=True)
        except git.exc.GitError as e:
            raise MigratorError("checkout of '{}' to commit '{}' failed:\n{}".format(self.repo_name(), commit_hash, e))

    def get_dependents(self, commit_or_hash):
        """ Get all commits that depend on a commit, including transitively

        Args:
            commit_or_hash (:obj:`str` or :obj:`git.objects.commit.Commit`): the hash of a commit or a commit
                in the repo

        Returns:
            :obj:`set` of :obj:`git.objects.commit.Commit`: all commits that depend on `commit_or_hash`
        """
        commit = self.get_commit(commit_or_hash)
        return ancestors(self.commit_DAG, commit)

    def commits_in_dependency_consistent_seq(self, commits):
        """ Order some git commits into a sequence that's consistent with the repo's dependencies

        Note that the sequence found is not deterministic, because nodes without dependency relationships
        can appear in any order. E.g., in a commit DAG with the paths a -> b -> c and a -> d -> c, nodes
        b and d can appear in either order in the sequece.

        Args:
            commits (:obj:`list` of :obj:`git.objects.commit.Commit`): commits to include in the
                returned sequence

        Returns:
            :obj:`list` of :obj:`git.objects.commit.Commit`: the elements of `commits`, in a sequence
                that's consistent with git commit dependencies in the repository, ordered from
                from antecedent to dependent
        """
        seq_with_schema_changes = []
        commits = set(commits)
        for commit in topological_sort(self.commit_DAG):
            if commit in commits:
                seq_with_schema_changes.append(commit)
        seq_with_schema_changes.reverse()
        return seq_with_schema_changes


# todo: add logging
# todo: consider workflow: someone changes the schema, & wants to easily migrate all data repos
class AutomatedMigration(object):
    """ Automate the migration of the data files in a repo

    A *data* repo stores the data files that need to be migrated. A *schema* repo contains the
    schemas that provide the data models for these data files. The *data* and *schema* repos may be
    the same repo or two different repos.

    The `data` repo contains a `migrations` directory that has:

    * At least one automated migration configuration file, written in YAML

    An automated migration configuration file contains the attributes described in `_CONFIG_ATTRIBUTES`:

    * The url of the `schema` repo
    * A list of files to be migrated
    * The path to the schema file in the `schema` repo
    * The type of migrator to use

    The `schema` repo contains a `migrations` directory that has:

    * Some schema changes files, which may refer to associated transformations files. Hashes
    in the changes files must refer to commits in the `schema` repo. These files are managed by
    `SchemaChanges` objects. Migration will not work if changes to the schema are not documented in
    a schems changes file.

    `AutomatedMigration` uses configuration information in the `data` and `schema` repos to migrate
    data files in the `data` repo to the latest version of the `schema` repo.

    Attributes:
        data_repo_location (:obj:`GitRepo`): directory or url of the *data* repo
        data_git_repo (:obj:`GitRepo`): a :obj:`GitRepo` for a git clone of the *data* repo
        schema_git_repo (:obj:`GitRepo`): a :obj:`GitRepo` for a clone of the current version of the *schema* repo
        data_config_file_basename (:obj:`str`): the basename of the YAML configuration file for the
            migration, which is stored in the *data* repo's migrations directory
        data_config (:obj:`dict`): the data in the automated migration config file
        loaded_schema_changes (:obj:`list`) all validated schema change files
        migration_spec (:obj:`MigrationSpec`): the migration's specification
    """

    # name of the git metadata configuration attribute in an obj_model schema
    _GIT_METADATA = '_GIT_METADATA'

    # name of the migrations directory
    _MIGRATIONS_DIRECTORY = 'migrations'

    # template for the name of a config file
    # the format placeholder is replaced with the name of the schema repo to which it refers
    _CONFIG_FILE = 'automated_migration_config-{}.yaml'

    # template for the name of an automated migration; the format placeholders are replaced with
    # 1) the name of the data repo, 2) the name of the schema repo, and 3) a datetime value
    # assumes that the filled values do not contain ':'
    _NAME_FORMAT = 'automated-migration:{}:{}:{}'

    # attributes in the automated migration configuration file
    _CONFIG_ATTRIBUTES = {
        # 'name': (type, description, default)
        'files_to_migrate': ('list', 'paths to files in the data repo to migrate', None),
        'schema_repo_url': ('str', 'the URL of the schema repo', None),
        'schema_file': ('str', 'the relative path to the schema file in the schema repo', None),
        'migrator': ('str',
            'the keyword for the type of migrator to use, a key in `MigrationSpec.MIGRATOR_CREATOR_MAP`',
            MigrationSpec.DEFAULT_MIGRATOR),
    }

    # attributes in a `AutomatedMigration`
    _ATTRIBUTES = ['data_repo_location', 'data_git_repo', 'schema_git_repo', 'data_config_file_basename',
        'data_config', 'loaded_schema_changes', 'migration_spec']
    _REQUIRED_ATTRIBUTES = ['data_repo_location', 'data_config_file_basename']

    def __init__(self, **kwargs):
        for attr in self._ATTRIBUTES:
            setattr(self, attr, None)

        # check that all required attributes are provided
        missing_attrs = set(self._REQUIRED_ATTRIBUTES) - set(kwargs)
        if missing_attrs:
            raise MigratorError("initialization of AutomatedMigration must provide "
                "AutomatedMigration._REQUIRED_ATTRIBUTES ({}) but these are missing: {}".format(
                self._REQUIRED_ATTRIBUTES, missing_attrs))

        # initialize attributes provided
        for attr, value in kwargs.items():
            setattr(self, attr, value)

        # get data repo
        self.data_git_repo = GitRepo(self.data_repo_location)

        # todo: determine data_config_file_basename automatically if there's only one
        # load data config file
        self.data_config = self.load_config_file(
            os.path.join(self.data_git_repo.migrations_dir(), self.data_config_file_basename))

        # clone and load schema repo
        self.schema_git_repo = GitRepo(self.data_config['schema_repo_url'])

    @staticmethod
    def make_template_config_file(data_git_repo, schema_repo_name):
        """ Create a template automated migration config file

        Args:
            data_git_repo (:obj:`GitRepo`): the data git repo that contains the data files to migrate
            schema_repo_name (:obj:`str`): name of schema repo

        Returns:
            :obj:`str`: the pathname to the template automated migration config file that was written

        Raises:
            :obj:`MigratorError`: if the automated migration configuration file already exists
        """
        pathname = os.path.join(data_git_repo.migrations_dir(),
            AutomatedMigration._CONFIG_FILE.format(schema_repo_name))
        if os.path.exists(pathname):
            raise MigratorError("automated migration configuration file '{}' already exists".format(pathname))

        # create the migrations directory if it doesn't exist
        os.makedirs(data_git_repo.migrations_dir(), exist_ok=True)

        config_data = {}
        for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
            attr_type, _, default = config_attr
            if attr_type == 'list':
                config_data[name] = []
            elif attr_type == 'str':
                if default:
                    config_data[name] = default
                else:
                    config_data[name] = ''
            else:
                None    # pragma: no cover; coverage can't be told that non-existent 'else' never happens

        with open(pathname, 'w') as file:
            file.write(u'# automated migration configuration file\n\n')
            # add documentation about the config file attributes
            file.write(u'# description of the attributes:\n')
            for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
                _, description, _ = config_attr
                file.write("# '{}' contains {}\n".format(name, description))

            # generate YAML content
            file.write(yaml.dump(config_data))

        # add the config to the git repo
        data_git_repo.repo.index.add([pathname])
        return pathname

    @staticmethod
    def load_config_file(automated_migration_config_file):
        """ Load an automated migration config file

        Args:
            automated_migration_config_file (:obj:`str`): path to the automated migration config file

        Returns:
            :obj:`dict`: the data in the automated migration config file

        Raises:
            :obj:`MigratorError`: if the automated migration config file cannot be found,
                or is not proper YAML,
                or does not have the right format,
                or does not contain any data
        """
        try:
            fd = open(automated_migration_config_file, 'r')
        except FileNotFoundError as e:
            raise MigratorError("could not read automated migration config file: '{}'".format(
                automated_migration_config_file))
        try:
            automated_migration_config = yaml.load(fd, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            raise MigratorError("could not parse YAML automated migration config file: '{}':\n{}".format(
                automated_migration_config_file, e))

        if not isinstance(automated_migration_config, dict) or \
            any([attr_name not in automated_migration_config for attr_name in AutomatedMigration._CONFIG_ATTRIBUTES]):
                raise MigratorError("automated migration config file must have a dict with the attributes in "
                    "{}._CONFIG_ATTRIBUTES: {}".format(AutomatedMigration.__name__,
                    ', '.join(AutomatedMigration._CONFIG_ATTRIBUTES)))

        # all attributes must be initialized
        if any([not automated_migration_config[attr_name] for attr_name in AutomatedMigration._CONFIG_ATTRIBUTES]):
                raise MigratorError("all attributes in an automated migration config file must be "
                    "initialized, but they are: {}".format(pformat(automated_migration_config)))

        return automated_migration_config

    def validate(self):
        """ Validate files to migrate, and load all schema changes files

        Args:
            automated_migration_config_file (:obj:`str`): path to the automated migration config file

        Returns:
            :obj:`dict`: the data in the automated migration config file

        Raises:
            :obj:`MigratorError`: if any files to migrate do not exist,
                or all schema changes files cannot be loaded
        """
        errors = []
        expanded_files_to_migrate = []
        for file in self.data_config['files_to_migrate']:
            abs_path = normalize_filename(file, dir=self.data_git_repo.migrations_dir())
            if not os.path.isfile(abs_path):
                errors.append("file to migrate '{}', with full path '{}', doesn't exist".format(file, abs_path))
            else:
                expanded_files_to_migrate.append(abs_path)
        if errors:
            raise MigratorError('\n'.join(errors))
        self.data_config['files_to_migrate'] = expanded_files_to_migrate

        # load all schema changes files & make sure each one corresponds to a hash
        errors, self.loaded_schema_changes = SchemaChanges.all_schema_changes_with_commits(self.schema_git_repo)
        if errors:
            raise MigratorError('\n'.join(errors))

    def get_name(self):
        """ Make a timestamped name for an automated migration

        Returns:
            :obj:`str`: the name

        Raises:
            :obj:`MigratorError`: if the data or the schema git repo is not initialized
        """
        if self.data_git_repo is None or self.schema_git_repo is None:
            raise MigratorError("To run get_name() data_git_repo and schema_git_repo must be initialized")
        return self._NAME_FORMAT.format(self.data_git_repo.repo_name(), self.schema_git_repo.repo_name(),
            SchemaChanges.get_date_timestamp())

    def get_data_file_git_commit_hash(self, data_file):
        """ Get the git commit hash of the schema repo that describes a data file

        The schema in `self.schema_git_repo` must specify a Model name and metadata attributes
        in a `_GIT_METADATA` attribute. E.g., `wc_lang` contains:
            `_GIT_METADATA = (Model, ('url', 'branch', 'revision'))`

        Args:
            data_file (:obj:`str`): name of a data file

        Returns:
            :obj:`str`: the hash

        Raises:
            :obj:`MigratorError`: if the schema in `self.schema_git_repo` lacks a `_GIT_METADATA` attribute
        """
        # get the schema in the self.schema_git_repo and schema_file in the automated migration config file
        schema_file = normalize_filename(self.data_config['schema_file'],
            dir=self.schema_git_repo.migrations_dir())
        schema_module = SchemaModule(schema_file)
        module = schema_module.import_module_for_migration()

        # use the schema to find the obj_model.Model storing the git metadata
        if not hasattr(module, AutomatedMigration._GIT_METADATA):
            raise MigratorError("schema '{}' does not have a {} attribute".format(schema_file,
                AutomatedMigration._GIT_METADATA))
        git_metadata = getattr(module, AutomatedMigration._GIT_METADATA)
        metadata_model_type = git_metadata[0]
        _, _, revision_attr = git_metadata[1]

        # use obj_model Reader to read the data file
        model_defs = schema_module.run()
        models = obj_model.io.Reader().run(data_file, models=list(model_defs.values()), ignore_extra_sheets=True,
            ignore_sheet_order=True, include_all_attributes=False, ignore_extra_attributes=True,
            ignore_attribute_order=True, group_objects_by_model=True, validate=False)
        # check that there's exactly 1 instance of the metadata_model_type
        if len(models[metadata_model_type]) != 1:
            raise MigratorError("data file '{}' must contain exactly one instance of {}, the Model "
                "containing the git metadata".format(data_file, metadata_model_type.__name__))
        metadata_model = models[metadata_model_type][0]
        commit_hash = getattr(metadata_model, revision_attr)
        return commit_hash

    def generate_migration_spec(self, data_file, schema_changes):
        """ Generate a `MigrationSpec` from a sequence of schema changes

        The migration will migrate the file in place.

        Args:
            data_file (:obj:`str`): the existing data file that will be migrated
            schema_changes (:obj:`list` of :obj:`SchemaChanges`): a sequence of schema changes

        Returns:
            :obj:`MigrationSpec`: a `MigrationSpec` to migrate the file through the sequence of schema changes

        Raises:
            :obj:`MigratorError`: if the `MigrationSpec` created does not validate
        """
        spec_args = {}
        # todo: more compact name
        spec_args['name'] = "{}:{}".format(data_file, self.get_name())
        spec_args['existing_files'] = [data_file]

        # get the schema for the data file
        git_repo = GitRepo(self.data_config['schema_repo_url'])
        commit_hash = self.get_data_file_git_commit_hash(data_file)
        git_repo.checkout_commit(commit_hash)
        data_file_schema_file = normalize_filename(self.data_config['schema_file'], dir=git_repo.migrations_dir())
        spec_args['schema_files'] = [data_file_schema_file]

        spec_args['seq_of_renamed_models'] = []
        spec_args['seq_of_renamed_attributes'] = []
        spec_args['seq_of_transformations'] = []
        for schema_change in schema_changes:
            # make separate clone of each schema commit
            git_repo = GitRepo(self.data_config['schema_repo_url'])
            git_repo.checkout_commit(schema_change.commit_hash)
            schema_file = normalize_filename(self.data_config['schema_file'], dir=git_repo.migrations_dir())
            spec_args['schema_files'].append(schema_file)
            spec_args['seq_of_renamed_models'].append(schema_change.renamed_models)
            spec_args['seq_of_renamed_attributes'].append(schema_change.renamed_attributes)
            spec_args['seq_of_transformations'].append(schema_change.transformations_file)

        spec_args['migrator'] = self.data_config['migrator']
        spec_args['migrate_in_place'] = True
        migration_spec = MigrationSpec(**spec_args)
        migration_spec.prepare()
        return migration_spec

    def schema_changes_for_data_file(self, data_file):
        """ Generate a sequence of `SchemaChanges` for migrating a data file

        Args:
            data_file (:obj:`str`): a data file in the data git repo

        Returns:
            :obj:`list`: a sequence of `SchemaChanges` for migrating a data file
        """
        # get the schema for the data file
        commit_hash = self.get_data_file_git_commit_hash(data_file)
        # schema_git_repo = GitRepo(self.data_config['schema_repo_url'])
        # schema_changes = SchemaChanges(git_repo=schema_git_repo, commit_hash=commit_hash)

        # make a SchemaChanges for each schema change in the file's schema's dependents
        hashes_of_schema_changes = [sc.commit_hash for sc in self.loaded_schema_changes]
        hashes_of_dependents = \
            [GitRepo.get_hash(dependent) for dependent in self.schema_git_repo.get_dependents(commit_hash)]
        hashes_of_dependent_schema_changes = set(hashes_of_schema_changes).intersection(hashes_of_dependents)
        commits = self.schema_git_repo.get_commits(hashes_of_dependent_schema_changes)

        # create a SchemaChanges for each migration of data_file
        seq_of_schema_changes = []
        for commit in self.schema_git_repo.commits_in_dependency_consistent_seq(commits):
            schema_changes_file = SchemaChanges.find_file(self.schema_git_repo, GitRepo.get_hash(commit))
            seq_of_schema_changes.append(SchemaChanges.generate_instance(schema_changes_file))
        return seq_of_schema_changes

    def prepare(self):
        """ Prepare for migration

        * Validate files to migrate, and load all schema changes files
        * Clone each schema change
        * Generate and prepare a migration spec for the migration
        """
        # todo: partition data files by their associated commit
        # temporarily, make a separate migration spec for each data file
        '''
        for each data file:
            make a migration spec
            determine file's commit and get its schema file
            make schema change with the commit & no changes
            for each schema change downstream in topo_sort from file's commit:
                get schema change (and add to migration spec)
        '''
        self.validate()
        self.migration_spec = self.generate_migration_spec(data_file)
        self.migration_spec.prepare()

    def migrate(self):
        """ Migrate the repo's data files

        By default, migrate to the current version of the schema repo, and migrate data files in place

        Returns:
            :obj:`list`: the migrated files
        """
        self.prepare()
        # migrate
        _, all_migrated_files = MigrationController.migrate_over_schema_sequence(self.migration_spec)
        # test the migration
        # todo: migrated files are in a tmp dir holding the data_git_repo; make them available to the user
        # the user might want to review the migrated data and then commit the changes
        # could copy the migrated files into a directory provided by the user
        return all_migrated_files

    def test(self):
        """ Test a migration

        """
        pass


class RunMigration(object):

    @staticmethod
    def parse_args(cli_args):
        """ Parse command line arguments

        Args:
            cli_args (:obj:`list`): command line arguments

        Returns:
            :obj:`argparse.Namespace`: parsed command line arguements
        """
        parser = argparse.ArgumentParser(
            description="Migrate model file(s) from an existing schema to a migrated one")
        parser.add_argument('migrations_config_file', help="migrations configured in YAML file")
        parser.add_argument('-w', '--warnings', action='store_true', help="show MigrateWarning warnings")
        args = parser.parse_args(cli_args)
        return args

    @staticmethod
    def main(args):
        if not args.warnings:
            warnings.simplefilter("ignore", category=MigrateWarning)
        results = MigrationController.migrate_from_config(args.migrations_config_file)
        for migration_disc, migrated_filenames in results:
            print("migrations in '{}':".format(migration_disc.name))
            for existing_file, migrated_file in zip(migration_disc.existing_files, migrated_filenames):
                print("    '{}' -> '{}'".format(existing_file, migrated_file))
        return results

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
