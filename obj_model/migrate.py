""" Support schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

from cement import Controller, App
from enum import Enum
from modulefinder import ModuleFinder
from networkx.algorithms.dag import topological_sort, ancestors
from pathlib import Path, PurePath
from pprint import pprint, pformat
from six import integer_types, string_types
from urllib.parse import urlparse
from warnings import warn
import argparse
import cement
import collections
import copy
import datetime
import git
import importlib
import importlib.util
import inspect
import networkx as nx
import os
import re
import shutil
import sys
import tempfile
import warnings
import yaml

from obj_model import (TabularOrientation, RelatedAttribute, get_models, SlugAttribute, StringAttribute,
    RegexAttribute, UrlAttribute, DateTimeAttribute)
from obj_model import utils
from obj_model.expression import ParsedExpression, ObjModelTokenCodes
from obj_model.io import TOC_NAME
from obj_model.io import WorkbookReader, IoWarning
from obj_model.units import UnitAttribute
from wc_utils.util.files import normalize_filename, remove_silently
from wc_utils.util.list import det_find_dupes, det_count_elements, dict_by_class
from wc_utils.workbook.io import read
import obj_model
import wc_utils

# TODOS
#
# refactor generate_wc_lang_migrator into method in wc_lang called by obj_model
#   define abstract migrator here, and let schema optionally subclass it
# check documentation

# todo: test OneToManyAttribute
# todo: would be more intuitive to express renamed_attributes as [ExistingModelName.existing_attr_name, MigratedModelName.migrated_attr_name]
# todo: remove SchemaModule.annotation, which isn't used
# todo: remove or formalize debugging in import_module_for_migration()
# JK ideas:
# todo: how original is obj_model.migration? literature search, ask David Nickerson, Pedro Mendez
# check SBML, Kappa, PySB, BioNetGet, SBML, COPASI, JWS-online, Simmune at NIH
# publicize work, in part to get feedback
# documentation note:
#   Migration is not composable. It should be run independently of other obj_model code.
# todo: automatically retry git requests, perhaps using the requests package

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
        annotation (:obj:`str`): an optional annotation, often the original path of a module
            that hass been copied; used for debugging
    """

    # cached schema modules that have been imported, indexed by full pathnames
    MODULES = {}
    # optional annotation for modules
    MODULE_ANNOTATIONS = {}

    def __init__(self, module_path, dir=None, annotation=None):
        """ Initialize a `SchemaModule`

        Args:
            module_path (:obj:`str`): path to the module
            dir (:obj:`str`, optional): a directory that contains `self.module_path`
            annotation (:obj:`str`, optional): an annotation about the schema
        """
        self.module_path = module_path
        self.abs_module_path = normalize_filename(self.module_path, dir=dir)
        self.directory, self.package_name, self.module_name = self.parse_module_path(self.abs_module_path)
        self.annotation = annotation

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
    def _munged_model_name(model):
        """ Provide munged name for `model`

        If `model`'s name is already munged, return the name.

        Args:
            model (:obj:`obj_model.Model`): a model

        Returns:
            :obj:`str`: a munged name for model, made by appending `SchemaModule.MUNGED_MODEL_NAME_SUFFIX`
        """
        if not SchemaModule._model_name_is_munged(model):
            return "{}{}".format(model.__name__, SchemaModule.MUNGED_MODEL_NAME_SUFFIX)
        else:
            return model.__name__

    @staticmethod
    def _unmunged_model_name(model):
        """ Provide unmunged name for `model`

        If `model`'s name isn't munged, return the name.

        Args:
            model (:obj:`obj_model.Model`): a model

        Returns:
            :obj:`str`: an unmunged name for `model`, made by removing the suffix
                `SchemaModule.MUNGED_MODEL_NAME_SUFFIX`
        """
        if SchemaModule._model_name_is_munged(model):
            return model.__name__[:-len(SchemaModule.MUNGED_MODEL_NAME_SUFFIX)]
        else:
            return model.__name__

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
            model.__name__ = SchemaModule._munged_model_name(model)

    @staticmethod
    def _unmunge_all_munged_model_names():
        """ Unmunge the names of all models so they can be used, inverting `_munge_all_model_names`
        """
        for model in get_models():
            model.__name__ = SchemaModule._unmunged_model_name(model)

    def import_module_for_migration(self, validate=True, required_attrs=None, debug=False,
        mod_patterns=None, print_code=False):
        """ Import a schema from a Python module in a file, which may be in a package

        Args:
            validate (:obj:`bool`, optional): whether to validate the module; default is `True`
            required_attrs (:obj:`list` of :obj:`str`, optional): list of attributes that must be
                present in the imported module
            debug (:obj:`bool`, optional): if true, print debugging output; default is `False`
            mod_patterns (:obj:`list` of :obj:`str`, optional): RE patterns used to search for
                modules in `sys.modules`; modules whose names match a pattern
                are output when `debug` is true
            print_code (:obj:`bool`, optional): if true, while debugging print code being imported;
                default is `False`

        Returns:
            :obj:`Module`: the `Module` loaded from `self.module_path`

        Raises:
            :obj:`MigratorError`: if the schema at `self.module_path` cannot be imported,
                or if validate is True and any related attribute in any model references a model
                    not in the module
                or if the module is missing a required attribute
        """
        if debug:
            print('\nimport_module_for_migration', self.module_name, self.annotation)
            if SchemaModule.MODULES:
                print('SchemaModule.MODULES:')
                for path, module in SchemaModule.MODULES.items():
                    name = module.__name__
                    package = module.__package__
                    if package:
                        name = package + '.' + name
                    print('\t', path, name)
                '''
                for path, module in SchemaModule.MODULES.items():
                    # todo: put this code for printing a module in a function & reuse below
                    name = getattr(module, '__name__')
                    package = getattr(module, '__package__')
                    if package:
                        name = package + '.' + name
                    file = module.__file__ if hasattr(module, '__file__') else ''
                    print('\t', name, file)
                    if path in SchemaModule.MODULE_ANNOTATIONS:
                        print('\t', 'annotation:', SchemaModule.MODULE_ANNOTATIONS[path])
                '''
            else:
                print('no SchemaModule.MODULES')

        # if a schema has already been imported, return its module so each schema has one internal representation
        if self.get_path() in SchemaModule.MODULES:
            if debug:
                print('reusing', self.get_path())
            return SchemaModule.MODULES[self.get_path()]

        # temporarily munge names of all models so they're not reused
        SchemaModule._munge_all_model_names()

        # copy sys.paths so it can be restored & sys.modules so new modules in self.module can be deleted
        sys_attrs = ['path', 'modules']
        saved = {}
        for sys_attr in sys_attrs:
            saved[sys_attr] = getattr(sys, sys_attr).copy()
        # temporarily put the directory holding the module being imported on sys.path
        sys.path.insert(0, self.directory)

        # todo: evaluate whether this suspension of check that related attribute names don't clash is still needed
        obj_model.core.ModelMeta.CHECK_SAME_RELATED_ATTRIBUTE_NAME = False

        def print_file(fn, max=100):
            print('\timporting: {}:'.format(fn))
            n = 0
            for line in open(fn, 'r').readlines():
                print('\t\t', line, end='')
                n += 1
                if max<=n:
                    print('\tExceeded max ({}) lines'.format(max))
                    break
            print()

        if debug:
            print('path:', self.get_path())
            i = 1
            targets = set('ChemicalStructure MolecularStructure Parameter DataValue'.split())
            for line in open(self.get_path(), 'r').readlines():
                i += 1
                for target in targets:
                    if 'class ' + target in line:
                        print('\t', i, ':', line, end='')
                        break

        if debug:
            print("\n== importing {} from '{}' ==".format(self.module_name, self.directory))
            if print_code:
                if '.' in self.module_name:
                    nested_modules = self.module_name.split('.')
                    for i in range(len(nested_modules)):
                        path = os.path.join(self.directory, *nested_modules[:i], '__init__.py')
                        if os.path.isfile(path):
                            print_file(path)
                self.module_name, self.directory
                print_file(self.get_path())

            if mod_patterns:
                if not isinstance(mod_patterns, collections.Iterable) or isinstance(mod_patterns, str):
                    raise MigratorError(
                        "mod_patterns must be an iterator that's not a string; but it is a(n) '{}'".format(
                        type(mod_patterns).__name__))
                print("sys.modules entries matching RE patterns: '{}':".format("', '".join(mod_patterns)))
                compiled_mod_patterns = [re.compile(mod_pattern) for mod_pattern in mod_patterns]
                for name, module in sys.modules.items():
                    for compiled_mod_pattern in compiled_mod_patterns:
                        if compiled_mod_pattern.search(name):
                            if hasattr(module, '__file__'):
                                print('\t', name, module.__file__)
                            else:
                                print('\t', name)
                            break

            if debug:
                print('sys.path:')
                for p in sys.path:
                    print('\t', p)
                print('import_module', self.module_name, self.annotation)

        try:
            new_module = importlib.import_module(self.module_name)

            if debug:
                models_found = set()
                names = set()
                for name, cls in inspect.getmembers(new_module, inspect.isclass):
                    names.add(name)
                    if issubclass(cls, obj_model.core.Model) and \
                        not cls in {obj_model.Model, obj_model.abstract.AbstractModel}:
                        models_found.add(name)
                print('targets in names', names.intersection(targets))
                print('targets in models_found', models_found.intersection(targets))

        except (SyntaxError, ImportError, AttributeError, ValueError, NameError) as e:
            raise MigratorError("'{}' cannot be imported and exec'ed: {}: {}".format(
                self.get_path(), e.__class__.__name__, e))
        finally:

            # reset global variable
            obj_model.core.ModelMeta.CHECK_SAME_RELATED_ATTRIBUTE_NAME = True

            # unmunge names of all models, so they're normal for all other wc code
            SchemaModule._unmunge_all_munged_model_names()

            # to avoid accessing the schema via other import statements restore sys.path
            sys.path = saved['path']

            # sort the set difference to make this code deterministic
            new_modules = sorted(set(sys.modules) - set(saved['modules']))
            if debug:
                if new_modules:
                    print('new modules:')
                    for k in new_modules:
                        module = sys.modules[k]
                        name = getattr(module, '__name__')
                        package = getattr(module, '__package__')
                        if package:
                            name = package + '.' + name
                        file = module.__file__ if hasattr(module, '__file__') else ''
                        print('\t', name, file)

                changed_modules = [k for k in set(sys.modules) & set(saved['modules'])
                    if sys.modules[k] != saved['modules'][k]]
                if changed_modules:
                    print('changed modules:')
                    for k in changed_modules:
                        print(k)

            # to enable the loading of many versions of schema modules, remove them from sys.modules
            # to improve performance, do not remove other modules
            def first_component_module_name(module_name):
                return module_name.split('.')[0]
            first_component_imported_module = first_component_module_name(self.module_name)
            for k in new_modules:
                if first_component_module_name(k) == first_component_imported_module:
                    del sys.modules[k]
            # leave changed modules alone

        if required_attrs:
            # module must have the required attributes
            errors = []
            for required_attr in required_attrs:
                if not hasattr(new_module, required_attr):
                    errors.append("module in '{}' missing required attribute '{}'".format(
                        self.get_path(), required_attr))
            if errors:
                raise MigratorError('\n'.join(errors))

        if validate:
            errors = self._check_imported_models(module=new_module)
            if errors:
                raise MigratorError('\n'.join(errors))

        # save an imported schema in SchemaModule.MODULES, indexed by its path
        # results will be unpredictable if different code is imported from the same path
        SchemaModule.MODULES[self.get_path()] = new_module
        # save the SchemaModule's annotation, if available
        if self.annotation:
            SchemaModule.MODULE_ANNOTATIONS[self.get_path()] = self.annotation

        return new_module

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
            migrated models; not used in any existing schema
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
        """ Initialize a `Migrator`s schemas from files

        Distinct from `prepare` so most of `Migrator` can be tested with models defined in code

        Returns:
            :obj:`list` of :obj:`obj_model.Model`: the `Model`s in `self.module_path`
        """
        if self.existing_schema:
            # print('getting existing_schema')
            self.existing_defs = self.existing_schema.run()
            # print('existing_defs', list(self.existing_defs.keys()))
        if self.migrated_schema:
            # print('getting migrated_schema')
            self.migrated_defs = self.migrated_schema.run()
            # print('migrated_defs', list(self.migrated_defs.keys()))
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

        # get attribute name not used in existing schemas so that existing models can point to migrated models
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

        # constraint: existing_model and migrated_model must be available in their respective schemas
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
        return [model for model in models.values() if model.Meta.tabular_orientation not in [TabularOrientation.cell, TabularOrientation.multiple_cells]]

    def read_existing_model(self, existing_file):
        """ Read models from existing file

        Does not perform validation -- data in existing model file must be already validated with the existing schema.

        Args:
            existing_file (:obj:`str`): pathname of file to migrate

        Returns:
            :obj:`list` of `obj_model.Model`: the models in `existing_file`
        """
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
        """ Migrate existing model instances to the migrated schema

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
        # todo: add data_repo_metadata=True
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
        """ Migrate all model instances from the existing schema to the migrated schema

        Supports:

        * delete attributes from the existing schema
        * add attributes in the migrated schema
        * add model definitions in the migrated schema
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

            # do not migrate model instances whose classes are not in the migrated schema
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
        git_hashes (:obj:`list` of :obj:`str`, optional): list of the git hashes of the git versions
            that contain the schemas
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
        'MIGRATOR_CREATOR_MAP', 'git_hashes']

    def __init__(self, name, migrator=DEFAULT_MIGRATOR, existing_files=None, schema_files=None,
        git_hashes=None, seq_of_renamed_models=None, seq_of_renamed_attributes=None, seq_of_transformations=None,
        migrated_files=None, migrate_suffix=None, migrate_in_place=False, migrations_config_file=None):
        self.name = name
        self.migrator = migrator
        self.existing_files = existing_files
        self.schema_files = schema_files
        self.git_hashes = git_hashes
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
            :obj:`MigratorError`: if `migrations_config_file` cannot be read, or the migration
                specifications in `migrations_config_file` are not valid
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
        for migration_name, migration_desc in migrations_config.items():
            migration_spec = MigrationSpec(migration_name, migrations_config_file=migrations_config_file)
            for param, value in migration_desc.items():
                setattr(migration_spec, param, value)
            migration_specs[migration_name] = migration_spec

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
            return ["a migration spec must contain at least 2 schemas, but it has only {}".format(
                len(self.schema_files))]

        if self.git_hashes and len(self.git_hashes) != len(self.schema_files):
            return ["a migration spec containing git hashes must have 1 hash for each schema "
                "file, but this spec has {} git hash(es) and {} schemas".format(
                    len(self.git_hashes), len(self.schema_files))]

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
        ms = migration_spec
        ms.is_prepared()

        # iterate over existing_files & migrated_files
        migrated_files = ms.migrated_files if ms.migrated_files else [None] * len(ms.existing_files)
        all_models, all_migrated_files = [], []
        for existing_file, migrated_file in zip(ms.existing_files, migrated_files):
            num_migrations = len(ms.schema_files) - 1
            # since 0 < num_migrations the next loop always executes and branch coverage reports that
            # the 'for' line doesn't jump to return; this cannot be annotated with 'pragma: no cover'
            for i in range(num_migrations):
                # create Migrator for each pair of schemas
                migrator_creator = migration_spec.get_migrator()
                migrator = migrator_creator(existing_defs_file=ms.schema_files[i],
                    migrated_defs_file=ms.schema_files[i+1], renamed_models=ms.seq_of_renamed_models[i],
                    renamed_attributes=ms.seq_of_renamed_attributes[i])
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
                        migrated_file=migrated_file, migrate_suffix=ms.migrate_suffix,
                        migrate_in_place=ms.migrate_in_place)
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
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

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

    More generally, a `SchemaChanges` should encode the set of changes to a schema over the sequence
    of git commits since the previous `SchemaChanges`.

    Attributes:
        _CHANGES_FILE_ATTRS (:obj:`list` of :obj:`str`): required attributes in a schema changes file
        _ATTRIBUTES (:obj:`list` of :obj:`str`): attributes in a `SchemaChanges` instance
        schema_repo (:obj:`GitRepo`): a Git repo that defines the data model (schema) of the data being
            migrated
        schema_changes_file (:obj:`str`): the schema changes file
        commit_hash (:obj:`str`): hash from a schema changes file
        renamed_models (:obj:`list`, optional): list of renamed models in the commit
        renamed_attributes (:obj:`list`, optional): list of renamed attributes in the commit
        transformations_file (:obj:`str`, optional): the name of a Python file containing transformations
        transformations (:obj:`dict`, optional): the transformations for a migration to the schema,
            in a dictionary of callables
    """
    _CHANGES_FILE_ATTRS = ['commit_hash', 'renamed_models', 'renamed_attributes', 'transformations_file']

    _ATTRIBUTES = ['schema_repo', 'transformations', 'schema_changes_file', 'commit_hash',
        'renamed_models', 'renamed_attributes', 'transformations_file']

    # template for the name of a schema changes file; the format placeholders are replaced
    # with the file's creation timestamp and the prefix of the commit's git hash, respectively
    _CHANGES_FILENAME_TEMPLATE = "schema_changes_{}_{}.yaml"
    _SHA1_LEN = 40

    def __init__(self, schema_repo=None, schema_changes_file=None, commit_hash=None, renamed_models=None,
        renamed_attributes=None, transformations_file=None):
        self.schema_repo = schema_repo
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
        return self.schema_repo.latest_hash()

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
    def all_schema_changes_with_commits(schema_repo):
        """ Instantiate all schema changes in a git repo

        Obtain all validated schema change files.

        Args:
            schema_repo (:obj:`GitRepo`): an initialized repo for the schema

        Returns:
            :obj:`tuple`: :obj:`list` of errors, :obj:`list` all validated schema change files
        """
        errors = []
        schema_changes_with_commits = []
        migrations_directory = schema_repo.migrations_dir()
        for sc_file in SchemaChanges.all_schema_changes_files(migrations_directory):
            try:
                hash_prefix = SchemaChanges.hash_prefix_from_sc_file(sc_file)
                sc_dict = SchemaChanges.load(sc_file)
                commit_hash = sc_dict['commit_hash']
                if GitRepo.hash_prefix(commit_hash) != hash_prefix:
                    errors.append("hash prefix in schema changes filename '{}' inconsistent "
                        "with hash in file: '{}'".format(sc_file, sc_dict['commit_hash']))
                    continue

                # ensure that the hash corresponds to a commit
                try:
                    schema_repo.get_commit(commit_hash)
                except MigratorError:
                    errors.append("the hash in '{}', which is '{}', isn't the hash of a commit".format(
                        sc_file, sc_dict['commit_hash']))
                    continue

                schema_changes_with_commits.append(SchemaChanges.generate_instance(sc_file))

            except MigratorError as e:
                errors.append(str(e))

        return errors, schema_changes_with_commits

    @staticmethod
    def find_file(schema_repo, commit_hash):
        """ Find a schema changes file in a git repo

        Args:
            schema_repo (:obj:`GitRepo`): an initialized repo for the schema
            commit_hash (:obj:`str`): a git commit hash

        Returns:
            :obj:`str`: the pathname of the file found

        Raises:
            :obj:`MigratorError`: if a file with the hash cannot be found, or multiple files
                have the hash
        """
        # search with glob
        pattern = SchemaChanges._CHANGES_FILENAME_TEMPLATE.format('*',
            GitRepo.hash_prefix(commit_hash))
        migrations_directory = schema_repo.migrations_dir()
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
        if GitRepo.hash_prefix(sc_dict['commit_hash']) != GitRepo.hash_prefix(commit_hash):
            raise MigratorError("hash prefix in schema changes filename '{}' inconsistent "
                "with hash in file: '{}'".format(schema_changes_file, sc_dict['commit_hash']))

        # ensure that the hash corresponds to a commit
        try:
            schema_repo.get_commit(commit_hash)
        except MigratorError:
            raise MigratorError("the hash in '{}', which is '{}', isn't the hash of a commit".format(
                schema_changes_file, sc_dict['commit_hash']))

        return schema_changes_file

    def generate_filename(self, commit_hash):
        """ Generate a filename for a template schema changes file

        Returns:
            :obj:`str`: the filename
        """
        return SchemaChanges._CHANGES_FILENAME_TEMPLATE.format(self.get_date_timestamp(),
            GitRepo.hash_prefix(commit_hash))

    def make_template(self, schema_url=None, commit_hash=None):
        """ Make a template schema changes file

        The template includes the repo hash which it describes and empty values for `SchemaChanges`
        attributes.

        Args:
            schema_url (:obj:`str`, optional): URL of the schema repo; if not provided, `self.schema_repo`
                must be already initialized
            commit_hash (:obj:`str`, optional): hash of the schema repo commit which the template
                schema changes file describes; default is the most recent commit

        Returns:
            :obj:`str`: pathname of the schema changes file that was written

        Raises:
            :obj:`MigratorError`: if a repo cannot be cloned from `schema_url`, or
                checked out from `commit_hash`, or
                the schema changes file already exists
        """
        if schema_url:
            # clone the schema at schema_url
            self.schema_repo = GitRepo(schema_url)
        else:
            if not self.schema_repo:
                raise MigratorError("schema_repo must be initialized")
        if commit_hash:
            # ensure that commit_hash exists
            self.schema_repo.get_commit(commit_hash)
        else:
            commit_hash = self.get_hash()

        filename = self.generate_filename(commit_hash)
        changes_file_dir = self.schema_repo.migrations_dir()
        # if changes_file_dir doesn't exist, make it
        os.makedirs(changes_file_dir, exist_ok=True)

        pathname = os.path.join(changes_file_dir, filename)
        if os.path.exists(pathname):
            raise MigratorError("schema changes file '{}' already exists".format(pathname))

        with open(pathname, 'w') as file:
            file.write(u'# schema changes file\n')
            file.write(u"# stored in '{}'\n\n".format(filename))
            # generate YAML content
            template_data = dict(
                commit_hash=commit_hash,
                renamed_models=[],
                renamed_attributes=[],
                transformations_file=''
            )
            file.write(yaml.dump(template_data))

        # add the config file to the git repo
        self.schema_repo.repo.index.add([pathname])
        return pathname

    @staticmethod
    def make_template_command(schema_dir, commit_hash=None):
        """ Make a template schema changes file with CLI input

        Args:
            schema_dir (:obj:`str`): directory of the schema repo
            commit_hash (:obj:`str`, optional): hash of the schema repo commit which the template
                schema changes file describes; default is the most recent commit

        Returns:
            :obj:`str`: pathname of the schema changes file that was written

        Raises:
            :obj:`MigratorError`: if a repo cannot be cloned from `schema_url`, or
                checked out from `commit_hash`, or
                the schema changes file already exists
        """

        # extract URL of schema repo from local repo clone
        schema_dir = os.path.abspath(schema_dir)
        if not os.path.isdir(schema_dir):
            raise MigratorError("schema_dir is not a directory: '{}'".format(schema_dir))
        git_repo = GitRepo(schema_dir)

        # create template schema changes file
        schema_changes = SchemaChanges(git_repo)
        schema_changes_template_file = schema_changes.make_template(commit_hash=commit_hash)
        return schema_changes_template_file

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
        """ Read a schema changes file

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

        # report empty schema changes files (unmodified templates)
        if schema_changes['renamed_models'] == [] and \
            schema_changes['renamed_attributes'] == [] and \
            schema_changes['transformations_file'] == '':
                raise MigratorError("schema changes file '{}' is empty (an unmodified template)".format(
                    schema_changes_file))

        schema_changes['schema_changes_file'] = schema_changes_file
        return schema_changes

    @staticmethod
    def validate(schema_changes_kwargs):
        """ Check that the attributes of the arguments to `SchemaChanges` have the right structure

        Args:
            schema_changes_kwargs (:obj:`dict`): kwargs arguments to `SchemaChanges` generated by loading a schema
                changes file

        Returns:
            :obj:`list`: errors in `schema_changes_kwargs`
        """
        # check types
        errors = []
        for str_attr in ['commit_hash', 'transformations_file']:
            if not isinstance(schema_changes_kwargs[str_attr], str):
                errors.append("{} must be a str, but is a(n) {}".format(
                    str_attr, type(schema_changes_kwargs[str_attr]).__name__))

        required_structure = "renamed_models must be a list of pairs of strings, but is '{}'"
        try:
            for renaming in schema_changes_kwargs['renamed_models']:
                if len(renaming) != 2 or not isinstance(renaming[0], str) or not isinstance(renaming[1], str):
                    errors.append(required_structure.format(schema_changes_kwargs['renamed_models']))
                    continue
        except TypeError as e:
            errors.append(required_structure.format(schema_changes_kwargs['renamed_models']) + ", "
                "and examining it raises a(n) '{}' error".format(str(e)))

        required_structure = ("renamed_attributes must be a list of pairs of pairs of "
            "strings, but is '{}'")
        renamed_attributes = schema_changes_kwargs['renamed_attributes']
        try:
            no_renamed_attributes_error = True
            for renaming in renamed_attributes:
                # a renaming should be like [['TestNew', 'new_existing_attr'], ['TestNew', 'existing_attr'], ...]
                existing, migrated = renaming
                for attr_name in existing, migrated:
                    if (len(attr_name) != 2 or not isinstance(attr_name[0], str) or \
                        not isinstance(attr_name[1], str)) and no_renamed_attributes_error:
                        errors.append(required_structure.format(renamed_attributes))
                        no_renamed_attributes_error = False
                        continue
        except (TypeError, ValueError) as e:
            errors.append(required_structure.format(renamed_attributes) + ", and examining "
                "it raises a(n) '{}' error".format(str(e)))

        if errors:
            return errors

        if len(schema_changes_kwargs['commit_hash']) != SchemaChanges._SHA1_LEN:
            errors.append("commit_hash is '{}', which isn't the right length for a "
                "git hash".format(schema_changes_kwargs['commit_hash']))

        return errors

    @staticmethod
    def generate_instance(schema_changes_file):
        """ Generate a `SchemaChanges` instance from a schema changes file

        Args:
            schema_changes_file (:obj:`str`): path to the schema changes file

        Returns:
            :obj:`SchemaChanges`: the `SchemaChanges` instance
        """
        schema_changes_kwargs = SchemaChanges.load(schema_changes_file)
        errors = SchemaChanges.validate(schema_changes_kwargs)
        if errors:
            raise MigratorError(
            "in schema changes file '{}':\n)".format(schema_changes_file, '\n'.join(errors)))
        return SchemaChanges(**schema_changes_kwargs)

    def __str__(self):
        """ Provide a string representation

        Returns:
            :obj:`str`: a string representation of this `SchemaChanges`
        """
        rv = []
        for attr in self._ATTRIBUTES:
            rv.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(rv)


class GitRepo(object):
    """ Methods for processing a git repo and its commit history

    Attributes:
        repo_dir (:obj:`str`): the repo's root directory
        repo_url (:obj:`str`): the repo's URL, if known
        branch (:obj:`str`): the repo's branch, if it was cloned
        original_location (:obj:`str`): the repo's original root directory or URL, used for debugging
        repo (:obj:`git.Repo`): the `GitPython` repo
        commit_DAG (:obj:`nx.classes.digraph.DiGraph`): `NetworkX` DAG of the repo's commit history
        git_hash_map (:obj:`dict`): map from each git hash in the repo to its commit
        temp_dirs (:obj:`list` of :obj:`str`): temporary directories that hold repo clones
    """
    # default repo name if name not known
    _NAME_UNKNOWN = 'name_unknown'

    # name of an empty subdirectory in a temp dir that can be used as a destination for `shutil.copytree()`
    EMPTY_SUBDIR = 'empty_subdir'

    _HASH_PREFIX_LEN = 7

    def __init__(self, repo_location=None, branch='master', search_parent_directories=False,
        original_location=None):
        """ Initialize a `GitRepo` from an existing Git repo

        If `repo_location` is a directory then use the Git repo in the directory. Otherwise it must
        be an URL and the repo is cloned into a temporary directory.

        Args:
            repo_location (:obj:`str`, optional): the location of the repo, either its directory or
                its URL
            branch (:obj:`str`, optional): branch to clone if `repo_location` is an URL; default is
                `master`
            search_parent_directories (:obj:`bool`, optional): `search_parent_directories` option to
                `git.Repo()`; if set and `repo_location` is a directory, then all of its parent
                directories will be searched for a valid repo; default=False
            original_location (:obj:`str`, optional): the original location of the repo, either its
                root directory or its URL

        Returns:
            :obj:`str`: root directory for the repo (which contains the .git directory)
        """
        self.commit_DAG = None
        self.git_hash_map = None
        self.temp_dirs = []
        self.repo = None
        self.repo_dir = None
        self.repo_url = None
        self.branch = branch
        self.original_location = original_location
        if repo_location:
            if os.path.isdir(repo_location):
                try:
                    self.repo = git.Repo(repo_location, search_parent_directories=search_parent_directories)
                except git.exc.GitError as e:
                    raise MigratorError("instantiating a git.Repo from directory '{}' failed".format(
                        repo_location))
                self.repo_dir = os.path.dirname(self.repo.git_dir)
            else:
                self.clone_repo_from_url(repo_location, branch=branch)
            self.commit_DAG = self.commits_as_graph()
            if self.original_location is None:
                self.original_location = repo_location

    def get_temp_dir(self):
        """ Get a temporary directory, which must eventually be deleted by calling `del_temp_dirs`

        Returns:
            :obj:`str`: the pathname to a temporary directory
        """
        temp_dir = tempfile.mkdtemp()
        self.temp_dirs.append(temp_dir)
        return temp_dir

    def del_temp_dirs(self):
        """ Delete the temp dirs created by `get_temp_dir`

        Returns:
            :obj:`str`: the pathname to a temporary directory
        """
        for temp_dir in self.temp_dirs:
            shutil.rmtree(temp_dir)

    def clone_repo_from_url(self, url, branch='master', directory=None):
        """ Clone a repo from an URL

        Args:
            url (:obj:`str`): URL for the repo
            branch (:obj:`str`, optional): branch to clone; default is `master`
            directory (:obj:`str`, optional): directory to hold the repo; if not provided, the repo
                is stored in a new temporary dir

        Returns:
            :obj:`tuple`: (:obj:`git.Repo`, :obj:`str`): the repo cloned, and its root directory

        Raises:
            :obj:`MigratorError`: if repo cannot be cloned from `url`
        """
        if directory is None:
            directory = self.get_temp_dir()
        elif not os.path.isdir(directory):
            raise MigratorError("'{}' is not a directory".format(directory))
        try:
            kwargs = {'branch': branch}
            repo = git.Repo.clone_from(url, directory, **kwargs)
        except Exception as e:
            raise MigratorError("repo cannot be cloned from '{}'\n{}".format(url, e))
        self.repo = repo
        self.repo_dir = directory
        self.repo_url = url
        self.branch = branch
        return repo, directory

    def copy(self, tmp_dir=None):
        """ Copy this `GitRepo` into a new directory

        For better performance use `copy()` instead of `GitRepo()` or `clone_repo_from_url()` if you
        need multiple copies of a repo, such as multiple instances checked out to different commits.
        This is an optimization because copying is faster than cloning over the network.
        To avoid `bytecode is stale` errors, doesn't copy `__pycache__` directories.

        Args:
            tmp_dir (:obj:`str`, optional): directory to hold the repo; if not provided, the repo
                will be stored in a new temporary dir

        Returns:
            :obj:`GitRepo`: a new `GitRepo` that's a copy of `self` in a new temporary directory
        """
        if tmp_dir is None:
            tmp_dir = self.get_temp_dir()
        elif not os.path.isdir(tmp_dir):
            raise MigratorError("'{}' is not a directory".format(tmp_dir))
        dst = os.path.join(tmp_dir, self.EMPTY_SUBDIR)
        if not self.repo_dir:
            raise MigratorError("cannot copy an empty GitRepo")
        shutil.copytree(self.repo_dir, dst, ignore=shutil.ignore_patterns('*__pycache__*'))
        return GitRepo(dst, original_location=self.original_location)

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
        # todo: get the name even if the repo is in tmp dir by using the original location
        return self._NAME_UNKNOWN

    def head_commit(self):
        """ Get the repo's head commit

        Returns:
            :obj:`git.objects.commit.Commit`: the repo's latest commit
        """
        return self.repo.head.commit

    def latest_hash(self):
        """ Get the hash of the repo's latest commit

        Returns:
            :obj:`str`: the latest commit's SHA1 hash
        """
        return self.get_hash(self.head_commit())

    def get_commit(self, commit_or_hash):
        """ Obtain a commit from its hash

        Also, if `commit_or_hash` is a commit, simply return it.

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
        raise MigratorError("commit_or_hash '{}' cannot be converted into a commit".format(commit_or_hash))

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
        """ Make a DAG for this repo's commit dependencies - edges point from dependent commit to parent commit

        The DAG contains all commits in the repo on which the latest commit depends. Also creates
        `git_hash_map`, a map from all git hashes to their commits.

        Returns:
            :obj:`nx.classes.digraph.DiGraph`: a DAG representing the repo commit history
        """
        self.git_hash_map = {}
        commit_graph = nx.DiGraph()
        latest = self.head_commit()
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
    def hash_prefix(hash):
        """ Get a commit hash's prefix

        Args:
            hash (:obj:`str`): git commit hash

        Returns:
            :obj:`str`: hash's prefix
        """
        return hash[:GitRepo._HASH_PREFIX_LEN]

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

        Use `checkout_commit` carefully. If it checks out a new commit, then other operations on the
        repo may behave differently.

        Args:
            commit_identifier (:obj:`git.objects.commit.Commit` or :obj:`str`): a commit or a commit's hash

        Raises:
            :obj:`MigratorError`: if the commit cannot be checked out
        """
        try:
            commit_hash = GitRepo.get_hash(self.get_commit(commit_identifier))
            # use git directly, as per https://gitpython.readthedocs.io/en/stable/tutorial.html#using-git-directly
            self.repo.git.checkout(commit_hash, detach=True)
        except git.exc.GitError as e:
            raise MigratorError("checkout of '{}' to commit '{}' failed:\n{}".format(self.repo_name(), commit_hash, e))

    def add_file(self, filename):
        """ Add a file to the index

        Args:
            filename (:obj:`str`): path to new file

        Raises:
            :obj:`MigratorError`: if the file cannot be added
        """
        try:
            self.repo.index.add([filename])
        except (OSError, git.exc.GitError) as e:
            raise MigratorError("adding file '{}' to repo '{}' failed:\n{}".format(
                filename, self.repo_name(), e))

    def commit_changes(self, message):
        """ Commit the changes in this repo

        Args:
            message (:obj:`str`): the commit message

        Raises:
            :obj:`MigratorError`: if the changes cannot be commited
        """
        try:
            self.repo.index.commit(message)
        except (git.exc.GitError, AttributeError) as e:
            raise MigratorError("commiting repo '{}' failed:\n{}".format(self.repo_name(), e))

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

    def __str__(self):
        """ Provide a string representation

        Returns:
            :obj:`str`: a string representation of this `GitRepo`
        """
        rv = []
        scalar_attrs = ['repo_dir', 'repo_url', 'repo']
        for attr in scalar_attrs:
            val = getattr(self, attr)
            if val:
                rv.append("{}: {}".format(attr, val))
            else:
                rv.append("{}: not initialized".format(attr))

        if self.repo:
            rv.append("latest commit:\n\thash: {}\n\tsummary: {}\n\tUT timestamp: {}".format(
                GitRepo.get_hash(self.head_commit()),
                self.head_commit().summary,
                datetime.datetime.fromtimestamp(self.head_commit().committed_date).strftime('%c')))

        if self.commit_DAG:
            rv.append("commit_DAG (child -> parent):\n\t{}".format(
                "\n\t".join(
                    ["{} -> {}".format(GitRepo.hash_prefix(GitRepo.get_hash(u)),
                        GitRepo.hash_prefix(GitRepo.get_hash(v)))
                            for (u, v) in self.commit_DAG.edges])))
        else:
            rv.append("commit_DAG: empty")

        if self.git_hash_map:
            rv.append("git_hash_map: {} entries".format(len(self.git_hash_map)))
        else:
            rv.append("git_hash_map: empty")

        if self.temp_dirs:
            rv.append("temp_dirs:\n\t{}".format("\n\t".join(self.temp_dirs)))
        else:
            rv.append("temp_dirs: none used")

        return '\n'.join(rv)


class AutomatedMigration(object):
    """ Automate the migration of the data files in a repo

    A *data* repo stores the data files that need to be migrated. A *schema* repo contains the
    schemas that provide the data models for these data files. The *data* and *schema* repos may be
    the same repo or two different repos.

    `AutomatedMigration` uses configuration information in the *data* and *schema* repos to migrate
    data files in the *data* repo to the latest version of the *schema* repo.

    The `data` repo must contain a `migrations` directory that has:

    * Automated migration configuration files, written in YAML

    An automated migration configuration file contains the attributes described in `AutomatedMigration._CONFIG_ATTRIBUTES`:

    * `files_to_migrate`: a list of files to be migrated
    * `schema_repo_url`: the URL of the `schema` repo
    * `branch`: the branch of the `schema` repo
    * `schema_file`: the relative path of the schema file in the `schema` repo
    * `migrator`: the type of migrator to use

    The `schema` repo contains a `migrations` directory that contains schema changes files, which
    may refer to associated transformations files. Hashes
    in the changes files must refer to commits in the `schema` repo. These files are managed by
    `SchemaChanges` objects. Migration will not work if changes to the schema are not documented in
    schema changes files.

    Attributes:
        data_repo_location (:obj:`str`): directory or URL of the *data* repo
        data_git_repo (:obj:`GitRepo`): a :obj:`GitRepo` for a git clone of the *data* repo
        schema_git_repo (:obj:`GitRepo`): a :obj:`GitRepo` for a clone of the *schema* repo
        data_config_file_basename (:obj:`str`): the basename of the YAML configuration file for the
            migration, which is stored in the *data* repo's migrations directory
        migration_config_data (:obj:`dict`): the data in the automated migration config file
        loaded_schema_changes (:obj:`list`): all validated schema change files
        migration_specs (:obj:`MigrationSpec`): the migration's specification
        git_repos (:obj:`list` of :obj:`GitRepo`): all `GitRepo`s create by this `AutomatedMigration`
    """

    # name of the migrations directory
    # todo: after upgrading to BBedit, rename to .migrations and change the repos
    _MIGRATIONS_DIRECTORY = 'migrations'

    # template for the name of an automated migration; the format placeholders are replaced with
    # 1) the name of the data repo, 2) the name of the schema repo, and 3) a datetime value
    # assumes that the filled values do not contain ':'
    _MIGRATION_CONF_NAME_TEMPLATE = 'automated-migration:{}:{}:{}.yaml'

    # attributes in the automated migration configuration file
    _CONFIG_ATTRIBUTES = {
        # 'name': (type, description, default)
        'files_to_migrate': ('list', 'paths to files in the data repo to migrate', None),
        'schema_repo_url': ('str', 'the URL of the schema repo', None),
        'branch': ('str', "the schema's branch", 'master'),
        'schema_file': ('str', 'the relative path to the schema file in the schema repo', None),
        'migrator': ('str',
            'the keyword for the type of migrator to use, a key in `MigrationSpec.MIGRATOR_CREATOR_MAP`',
            MigrationSpec.DEFAULT_MIGRATOR),
    }

    # attributes in a `AutomatedMigration`
    _ATTRIBUTES = ['data_repo_location', 'data_git_repo', 'schema_git_repo', 'data_config_file_basename',
        'migration_config_data', 'loaded_schema_changes', 'migration_specs', 'git_repos']
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

        self.git_repos = []

        # get data repo
        self.data_git_repo = GitRepo(self.data_repo_location)
        self.record_git_repo(self.data_git_repo)

        # todo: determine data_config_file_basename automatically if there's only one in the data repo
        # load data config file
        self.migration_config_data = self.load_config_file(
            os.path.join(self.data_git_repo.migrations_dir(), self.data_config_file_basename))

        # clone and load the schema repo
        self.schema_git_repo = GitRepo(self.migration_config_data['schema_repo_url'],
            branch=self.migration_config_data['branch'])
        self.record_git_repo(self.schema_git_repo)

    @staticmethod
    def make_migration_config_file(data_git_repo, schema_repo_name, add_to_repo=True, **kwargs):
        """ Create an automated migration config file

        Args:
            data_git_repo (:obj:`GitRepo`): the data git repo that contains the data files to migrate
            schema_repo_name (:obj:`str`): name of the schema repo
            add_to_repo (:obj:`bool`, optional): if set, add the migration config file to the data repo;
                default = :obj:`True`:
            kwargs (:obj:`dict`): optional initial values for automated migration config file

        Returns:
            :obj:`str`: the pathname to the automated migration config file that was written

        Raises:
            :obj:`MigratorError`: if the automated migration configuration file already exists
        """
        pathname = os.path.join(data_git_repo.migrations_dir(),
            AutomatedMigration.get_name_static(data_git_repo.repo_name(), schema_repo_name))
        if os.path.exists(pathname):
            raise MigratorError("automated migration configuration file '{}' already exists".format(pathname))

        # create the migrations directory if it doesn't exist
        os.makedirs(data_git_repo.migrations_dir(), exist_ok=True)

        config_data = {}
        for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
            attr_type, _, default = config_attr
            default = default or eval(attr_type+'()')
            val = kwargs[name] if name in kwargs else default
            config_data[name] = val

        with open(pathname, 'w') as file:
            file.write(u'# automated migration configuration file\n\n')
            # add documentation about the config file attributes
            file.write(u'# description of the attributes:\n')
            for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
                _, description, _ = config_attr
                file.write("# '{}' contains {}\n".format(name, description))

            # generate YAML content
            file.write(yaml.dump(config_data))

        if add_to_repo:
            # add the automated migration configuration file to the data git repo
            data_git_repo.repo.index.add([pathname])
        return pathname

    @staticmethod
    def make_migration_config_file_command(data_repo_dir, schema_file_url, files_to_migrate, add_to_repo=True):
        """ Make an automated migration configuration file from CLI input

        Args:
            data_repo_dir (:obj:`str`): directory of the data repo
            schema_file_url (:obj:`str`): URL for schema's Python file
            files_to_migrate (:obj:`list` of :obj:`str`): data files to migrate
            add_to_repo (:obj:`bool`, optional): if set, add the migration config file to the data repo;
                default = :obj:`True`:

        Returns:
            :obj:`str`: pathname of the schema changes file that was written

        Raises:
            :obj:`MigratorError`: if `data_repo_dir` isn't the directory of a repo, or
                `schema_file_url` isn't the URL of a schema file, or
                `files_to_migrate` aren't files
        """
        data_repo_dir = os.path.abspath(data_repo_dir)
        ### convert schema_file_url into URL for schema repo & relative path to schema's Python file ###
        migration_config_file_kwargs = {}
        parsed_url = urlparse(schema_file_url)
        # error checks
        form = "scheme://git_website/organization/repo_name/'blob'/branch/relative_pathname"
        error_msg = "schema_file_url must be URL for python schema file, of the form: {}".format(form)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise MigratorError(error_msg)
        elements = parsed_url.path.split('/')
        if len(elements) < 6 or not schema_file_url.endswith('.py'):
            raise MigratorError(error_msg)
        schema_repo_url = parsed_url.scheme + '://' + parsed_url.netloc + '/' + '/'.join(elements[1:3])
        migration_config_file_kwargs['schema_repo_url'] = schema_repo_url
        schema_repo_name = elements[2]
        branch = elements[4]
        migration_config_file_kwargs['branch'] = branch
        # strip first two elements from schema_path: 'blob'/branch
        schema_file = '/'.join(elements[5:])
        migration_config_file_kwargs['schema_file'] = os.path.join('..', schema_file)

        ### extract URL of data repo from local repo clone ###
        if not os.path.isdir(data_repo_dir):
            raise MigratorError("data_repo_dir is not a directory: '{}'".format(data_repo_dir))
        git_repo = GitRepo(data_repo_dir)

        ### convert each data_file into path relative to migrations dir of data repo ###
        data_repo_root_dir = git_repo.repo_dir
        converted_data_files = []
        errors = []
        for data_file in files_to_migrate:
            # get full path
            normalized_data_file = normalize_filename(data_file, dir=data_repo_dir)
            if not os.path.isfile(normalized_data_file):
                errors.append("cannot find data file: '{}'".format(data_file))
                continue
            # get path relative to migrations dir
            relative_path = str(PurePath(normalized_data_file).relative_to(data_repo_root_dir))
            relative_path = os.path.join('..', relative_path)
            converted_data_files.append(relative_path)
        if errors:
            raise MigratorError('\n'.join(errors))
        migration_config_file_kwargs['files_to_migrate'] = converted_data_files

        ### determine migrator from name of schema ###
        # todo: store this mapping in a config file
        migrator_map = dict(
            wc_lang='wc_lang',
            wc_kb='wc_lang',
        )
        if schema_repo_name in migrator_map:
            migration_config_file_kwargs['migrator'] = migrator_map[schema_repo_name]

        ### create automated migration config file ###
        config_file_path = AutomatedMigration.make_migration_config_file(
            git_repo,
            schema_repo_name,
            add_to_repo=add_to_repo,
            **migration_config_file_kwargs)
        return config_file_path

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

        errors = []
        if not isinstance(automated_migration_config, dict):
            errors.append('yaml does not contain a dictionary')
        else:
            for attr_name in AutomatedMigration._CONFIG_ATTRIBUTES:
                if attr_name not in automated_migration_config:
                    errors.append("missing AutomatedMigration._CONFIG_ATTRIBUTES attribute: '{}'".format(
                        attr_name))
                elif not automated_migration_config[attr_name]:
                    # all attributes must be initialized
                    errors.append("uninitialized AutomatedMigration._CONFIG_ATTRIBUTES attribute: '{}'".format(
                        attr_name))
        if errors:
            raise MigratorError("invalid automated migration config file: '{}'\n{}".format(
                automated_migration_config_file, '\n'.join(errors)))

        return automated_migration_config

    def record_git_repo(self, git_repo):
        """ Record a new :obj:`GitRepo`: so that its temp dir can be deleted later

        Args:
            git_repo (:obj:`GitRepo`): a git repo
        """
        self.git_repos.append(git_repo)

    def clean_up(self):
        """ Delete the temp dirs used by this `AutomatedMigration`'s git repos
        """
        for git_repo in self.git_repos:
            git_repo.del_temp_dirs()

    def validate(self):
        """ Validate files to migrate, and load all schema changes files

        Raises:
            :obj:`MigratorError`: if any files to migrate do not exist,
                or all schema changes files cannot be loaded
        """
        errors = []
        expanded_files_to_migrate = []
        for file in self.migration_config_data['files_to_migrate']:
            abs_path = normalize_filename(file, dir=self.data_git_repo.migrations_dir())
            if not os.path.isfile(abs_path):
                errors.append("file to migrate '{}', with full path '{}', doesn't exist".format(file, abs_path))
            else:
                expanded_files_to_migrate.append(abs_path)
        if errors:
            raise MigratorError('\n'.join(errors))
        self.migration_config_data['files_to_migrate'] = expanded_files_to_migrate

        # load all schema changes files & make sure each one corresponds to a hash
        errors, self.loaded_schema_changes = SchemaChanges.all_schema_changes_with_commits(self.schema_git_repo)
        if errors:
            raise MigratorError('\n'.join(errors))

    def get_name(self):
        """ Make a timestamped name for an automated migration

        Returns:
            :obj:`str`: the name

        Raises:
            :obj:`MigratorError`: if either the data or the schema git repo are not initialized
        """
        if self.data_git_repo is None or self.schema_git_repo is None:
            raise MigratorError("To run get_name() data_git_repo and schema_git_repo must be initialized")
        return self.get_name_static(self.data_git_repo.repo_name(), self.schema_git_repo.repo_name())

    @staticmethod
    def get_name_static(data_repo_name, schema_repo_name):
        """ Make a timestamped name for an automated migration

        Args:
            data_repo_name (:obj:`str`): name of the data repo
            schema_repo_name (:obj:`str`): name of the schema repo

        Returns:
            :obj:`str`: the name
        """
        return AutomatedMigration._MIGRATION_CONF_NAME_TEMPLATE.format(data_repo_name,
            schema_repo_name, SchemaChanges.get_date_timestamp())

    def get_data_file_git_commit_hash(self, data_file):
        """ Get the git commit hash of the schema repo that describes a data file

        Args:
            data_file (:obj:`str`): pathname of a data file

        Returns:
            :obj:`str`: the hash

        Raises:
            :obj:`MigratorError`: if `data_file` does not contain a schema repo metadata model
        """
        try:
            metadata = utils.read_metadata_from_file(data_file)
        except Exception as e:
             raise MigratorError("Cannot get schema repo commit hash for '{}':\n{}".format(data_file, e))
        if metadata.schema_repo_metadata:
            return metadata.schema_repo_metadata.revision
        else:
            raise MigratorError("No schema repo commit hash in '{}'".format(data_file))

    def generate_migration_spec(self, data_file, schema_changes):
        """ Generate a `MigrationSpec` from a sequence of schema changes

        The migration will migrate `data_file` in place.

        Args:
            data_file (:obj:`str`): the existing data file that will be migrated
            schema_changes (:obj:`list` of :obj:`SchemaChanges`): a sequence of schema changes instances

        Returns:
            :obj:`MigrationSpec`: a `MigrationSpec` that specifies a migration of the file through
                the sequence of schema changes

        Raises:
            :obj:`MigratorError`: if the `MigrationSpec` that's created doesn't validate
        """
        spec_args = {}
        spec_args['name'] = "{}:{}".format(data_file, self.get_name())
        spec_args['existing_files'] = [data_file]

        # get the schema for the data file
        commit_hash = self.get_data_file_git_commit_hash(data_file)
        git_repo = self.schema_git_repo.copy()
        self.record_git_repo(git_repo)
        git_repo.checkout_commit(commit_hash)
        data_file_schema_file = normalize_filename(self.migration_config_data['schema_file'], dir=git_repo.migrations_dir())
        spec_args['schema_files'] = [data_file_schema_file]
        spec_args['git_hashes'] = [commit_hash]

        spec_args['seq_of_renamed_models'] = []
        spec_args['seq_of_renamed_attributes'] = []
        spec_args['seq_of_transformations'] = []
        for schema_change in schema_changes:
            # make a copy of each schema commit
            git_repo = self.schema_git_repo.copy()
            self.record_git_repo(git_repo)
            git_repo.checkout_commit(schema_change.commit_hash)
            schema_file = normalize_filename(self.migration_config_data['schema_file'], dir=git_repo.migrations_dir())
            spec_args['schema_files'].append(schema_file)
            spec_args['git_hashes'].append(schema_change.commit_hash)
            spec_args['seq_of_renamed_models'].append(schema_change.renamed_models)
            spec_args['seq_of_renamed_attributes'].append(schema_change.renamed_attributes)
            spec_args['seq_of_transformations'].append(schema_change.transformations_file)

        spec_args['migrator'] = self.migration_config_data['migrator']
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

        # make a SchemaChanges for each schema change in the file's schema dependents
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

        * Validate this `AutomatedMigration`
        * Clone each schema version specified by a schema change
        * Generate and prepare :obj:`MigrationSpec`: instances for the migration, one for each file

        Raises:
            :obj:`MigratorError`: if the `AutomatedMigration` doesn't validate
        """
        self.validate()
        self.migration_specs = []
        for file_to_migrate in self.migration_config_data['files_to_migrate']:
            schema_changes = self.schema_changes_for_data_file(file_to_migrate)
            migration_spec = self.generate_migration_spec(file_to_migrate, schema_changes)
            self.migration_specs.append(migration_spec)

    def automated_migrate(self, tmp_dir=None):
        """ Migrate the *data* repo's data files

        Migrate to the current version of the *schema* repo, and migrate data files in place.
        If the *data* repo passed to `AutomatedMigration` was a directory, then the migrated
        data files will be stored in that directory.

        Args:
            tmp_dir (:obj:`str`, optional): if the data repo passed to `AutomatedMigration` was an URL,
                then the migrated files will be returned in a temporary directory.
                If `tmp_dir` is provided then it will contain the migrated files; if not, then
                a temporary directory is created to hold them, and the caller is responsible for
                deleting it.

        Returns:
            :obj:`tuple` of :obj:`list`, :obj:`str`: the migrated files, and the value of `tmp_dir`
        """
        self.prepare()
        # migrate
        all_migrated_files = []
        for migration_spec in self.migration_specs:
            migrated_filenames = MigrationController.migrate_from_spec(migration_spec)
            single_migrated_file = migrated_filenames[0]
            all_migrated_files.append(single_migrated_file)

        if not os.path.isdir(self.data_repo_location):
            # data repo is in a temp dir made by GitRepo.clone_repo_from_url -- copy migrated files to tmp_dir
            dest_files = []
            if tmp_dir is None:
                tmp_dir = tempfile.mkdtemp()
            for migrated_file in all_migrated_files:
                # migrated_file is relative to self.data_git_repo.repo_dir
                relative_migrated_file = os.path.relpath(migrated_file, self.data_git_repo.repo_dir)
                dest = os.path.join(tmp_dir, relative_migrated_file)
                dest_files.append(dest)
                os.makedirs(os.path.dirname(dest))
                # copy migrated_file
                shutil.copyfile(migrated_file, dest)
        self.clean_up()

        # return the paths of the migrated files
        if not os.path.isdir(self.data_repo_location):
            return dest_files, tmp_dir
        else:
            return all_migrated_files, tmp_dir

    def verify_schemas(self):
        """ Verify that each schema can be independently imported

        It can be difficult to import a schema via `importlib.import_module()` in
        `import_module_for_migration()`. This method tests that proactively.

        Returns:
            :obj:`list` of :obj:`str`: all errors obtained
        """
        self.prepare()
        errors = []
        for migration_spec in self.migration_specs:
            for schema_file in migration_spec.schema_files:
                try:
                    SchemaModule(schema_file).import_module_for_migration()
                except MigratorError as e:
                    errors.append("cannot import: '{}'\n\t{}".format(schema_file, e))
        return errors

    @staticmethod
    def migrate_files(schema_url, local_dir, data_files):
        """ Migrate some data files specified by command line input

        Migrate data files in place in a local repository.

        Args:
            schema_url (:obj:`str`): URL of the schema's Python file
            local_dir (:obj:`str`): directory in a local data repo that contains the data files
            data_files (:obj:`list` of :obj:`str`): data files to migrate

        Returns:
            :obj:`list` of :obj:`str`: list of pathnames of migrated files

        Raises:
            :obj:`MigratorError`: if `schema_url` isn't in the right form, or
                `local_dir` isn't a directory, or
                any of the data files cannot be found, or
                the migration fails
        """
        local_dir = os.path.abspath(local_dir)
        config_file_path = AutomatedMigration.make_migration_config_file_command(local_dir, schema_url,
            data_files, add_to_repo=False)

        ### create and run AutomatedMigration ###
        automated_migration = AutomatedMigration(data_repo_location=local_dir,
            data_config_file_basename=os.path.basename(config_file_path))
        migrated_files, _ = automated_migration.automated_migrate()
        # delete the temporary automated migration config file
        remove_silently(config_file_path)
        return migrated_files

    def test_migration(self):
        """ Test a migration

        Check ...

        The trickiest part of a migration is importing the schema. Unfortunately, imports that use the Python `import`
        command may fail with migration's import, which uses the library call `importlib.import_module`. This should be called
        whenever a schema that may be migrated is changed.

        This method reports:

        * any validation errors in automatic config files
        * any validation errors in schema changes files
        * any errors in transformations
        * any failures to import schemas

        It does not alter any files.

        Args:
            data_repo_location (:obj:`str`): directory or URL of the *data* repo
        """
        '''
        todo:
            ensure that all of these are OK:
                automatic config files
                schema changes files
                transformations
                schemas
        '''

    def __str__(self):
        """ Provide a string representation

        Returns:
            :obj:`str`: a string representation of this `AutomatedMigration`
        """
        rv = []
        for attr in self._ATTRIBUTES:
            rv.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(rv)


class Utils(object):    # pragma: no cover
    """ Utilities for migration """

    @staticmethod
    def find_schema_modules():
        """ Find the modules used by a schema

        Useful for creating schema changes files for a schema repo

        Returns:
            :obj:`argparse.Namespace`: ???
        """
        parser = argparse.ArgumentParser(
            description="Find the modules used by a schema, and their commits")
        parser.add_argument('schema_path', help="path to a Python schema")
        parser.add_argument('repo', help="name of the repo")
        parser.add_argument('-p', '--paths', help="generate list of paths", action="store_true")
        args = parser.parse_args()
        finder = ModuleFinder()
        finder.run_script(args.schema_path)
        if not args.paths:
            max_name = 0
            max_path = 0
            for name, module in finder.modules.items():
                if module.__file__ and module.__file__.startswith(args.repo):
                    max_name = max(max_name, len(module.__name__))
                    max_path = max(max_path, len(module.__file__))
            custom_format = "{{:<{}}}{{:<{}}}".format(max_name+4, max_path)
            missing, maybe = finder.any_missing_maybe()
            wc_missing = [missin for missin in missing if 'wc_' in missin]
            if wc_missing:
                print('wc_missing:')
                for name in wc_missing:
                    print(name)
            else:
                print('no wc_missing')
            wc_maybe = [perhaps for perhaps in maybe if 'wc_' in perhaps]
            if wc_maybe:
                print('wc_maybe:')
                for name in wc_maybe:
                    print(name)
            else:
                print('no wc_maybe')

            print(custom_format.format('module name', 'module filename'))
            for name, module in finder.modules.items():
                if module.__file__ and module.__file__.startswith(args.repo):
                    print(custom_format.format(module.__name__, module.__file__))
        else:
            paths = []
            for module in finder.modules.values():
                if module.__file__ and module.__file__.startswith(args.repo):
                    paths.append(module.__file__)
            print(' '.join(paths))


class BaseController(cement.Controller):
    """ Base controller for command line application """

    class Meta:
        label = 'base'
        description = "Base controller for command line migration"

    @cement.ex(hide=True)
    def _default(self):
        self._parser.print_help()


# todo: add a controller that tests all migrations configured in migration config files
class CementControllers(object):
    """ Cement Controllers for CLIs in repos involved with migrating files whose data models are defined using `obj_model`

    Because these controllers are used by multiple schema and data repos, they're defined here and
    imported into `__main__.py` modules in schema repos that define data schemas and/or into `__main__.py`
    modules in data repos that contain data files to migrate. `wc_lang` is an example schema repo and
    `wc_sim` is a data repo that contains data files whose data model is defined in `wc_lang`.
    """

    class SchemaChangesTemplateController(Controller):
        """ Create a template schema changes file

        This controller is used by schema repos.
        """

        class Meta:
            label = 'make-changes-template'
            description = 'Create a template schema changes file'
            help = 'Create a template schema changes file'
            stacked_on = 'base'
            stacked_type = 'nested'
            arguments = [
                (['--schema_repo_dir'],
                    {'type': str,
                        'help': "path of the directory of the schema's repository; defaults to the "
                            "current directory",
                        'default': '.'}),
                (['--commit'],
                    {'type': str,
                        'help': "hash of a commit containing the changes; default is most recent commit"}),
            ]

        @cement.ex(hide=True)
        def _default(self):
            """ Make a template schema changes file in the schema repo

            Outputs the path of the template schema changes file that's created, or error(s) produced.
            """
            args = self.app.pargs
            schema_changes_template_file = SchemaChanges.make_template_command(args.schema_repo_dir,
                commit_hash=args.commit)
            # print directions to complete creating, commit & push the schema changes template file
            print("Created and added template schema changes file: '{}'.".format(schema_changes_template_file))
            print("Describe the schema changes in the file's attributes (renamed_attributes, "
                "renamed_models, and transformations_file). Then commit and push it with git.")


    class AutomatedMigrationConfigController(Controller):
        """ Create a migration configuration file

        This controller is used by data repos.
        """

        class Meta:
            label = 'make-migration-config-file'
            description='Create a migration configuration file'
            help='Create a migration configuration file'
            stacked_on = 'base'
            stacked_type = 'nested'
            arguments = [
                (['--data_repo_dir'],
                    {'type': str,
                        'help': "path of the directory of the repository storing the data file(s) to migrate; "
                            "defaults to the current directory",
                        'default': '.'}),
                (['schema_url'], {'type': str,
                    'help': 'URL of the schema in its git repository, including the branch'}),
                (['file_to_migrate'],
                    dict(action='store', type=str, nargs='+', help='a file to migrate')),
            ]

        @cement.ex(hide=True)
        def _default(self):
            args = self.app.pargs
            # args.file_to_migrate is a list of all files to migrate
            migration_config_file = AutomatedMigration.make_migration_config_file_command(args.data_repo_dir,
                args.schema_url, args.file_to_migrate)
            # print directions to commit & push the migration config file
            print("Automated migration config file created: '{}'".format(migration_config_file))
            print("Commit and push it with git.")


    class MigrateController(Controller):
        """ Perform a migration configured by a migration config file

        This controller is used by data repos.
        """

        class Meta:
            label = 'do-configured-migration'
            description='Migrate data file(s) as configured in a migration configuration file'
            help='Migrate data file(s) as configured in a migration configuration file'
            stacked_on = 'base'
            stacked_type = 'nested'
            arguments = [
                (['migration_config_file'],
                    {'type': str, 'help': 'name of the migration configuration file to use'})
            ]

        @cement.ex(hide=True)
        def _default(self):
            args = self.app.pargs
            migration_config_basename = Path(args.migration_config_file).name
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=MigrateWarning)
                automated_migration = AutomatedMigration(
                    **dict(data_repo_location='.', data_config_file_basename=migration_config_basename))
                migrated_files, _ = automated_migration.automated_migrate()

                for migrated_file in migrated_files:
                    print("'{}' migrated in place".format(migrated_file))


    class MigrateFileController(Controller):
        """ Migrate specified data file(s)

        This controller is used by data repos.
        """

        class Meta:
            label = 'migrate-data'
            description='Migrate specified data file(s)'
            help='Migrate specified data file(s)'
            stacked_on = 'base'
            stacked_type = 'nested'
            arguments = [
                (['--data_repo_dir'],
                    {'type': str,
                        'help': "path of the directory of the repository storing the data file(s) to migrate; "
                            "defaults to the current directory",
                        'default': '.'}),
                (['schema_url'], {'type': str,
                    'help': 'URL of the schema in its git repository, including the branch'}),
                (['file_to_migrate'],
                    dict(action='store', type=str, nargs='+',
                    help='a file to migrate')),
            ]

        @cement.ex(hide=True)
        def _default(self):
            args = self.app.pargs
            # args.file_to_migrate is a list of all files to migrate
            migrated_files = AutomatedMigration.migrate_files(args.schema_url, args.data_repo_dir,
                args.file_to_migrate)
            print('migrated files:')
            for migrated_file in migrated_files:
                print(migrated_file)


    # todo: cleanup: use a semantic comparison of model instances
    # until then, not useful, as reports changes in order and the presence of blanks
    class CompareFilesController(Controller):
        """ Compare a pair of data files

        This controller is used by data repos.
        """

        class Meta:
            label = 'compare-data-files'
            description='Compare the data content of two data files'
            help='Compare the data content of two data files'
            stacked_on = 'base'
            stacked_type = 'nested'
            arguments = [
                (['data_file_1'], {'type': str, 'help': 'first data file'}),
                (['data_file_2'], {'type': str, 'help': 'second data file'}),
                (['--differences'],
                    dict(
                        dest='differences', action='store_true',
                            help="output any differences between the files"))
            ]

        @cement.ex(hide=True)
        def _default(self):     # pragma: no cover
            args = self.app.pargs
            files_to_compare = []
            errors = []
            for data_file in [args.data_file_1, args.data_file_2]:
                # get full paths
                normalized_data_file = normalize_filename(data_file, dir=os.getcwd())
                if not os.path.isfile(normalized_data_file):
                    errors.append("cannot find data file: '{}'".format(data_file))
                    continue
                files_to_compare.append(normalized_data_file)
            if errors:
                raise MigratorError(';'.join(errors))

            workbook_1 = read(files_to_compare[0])
            workbook_2 = read(files_to_compare[1])

            for wb in [workbook_1, workbook_2]:
                if TOC_NAME in wb:
                    wb.pop(TOC_NAME)

                for metadata_sheet_name in ['Data repo metadata', 'Schema repo metadata']:
                    if metadata_sheet_name in wb:
                        wb.pop(metadata_sheet_name)

            if workbook_1 == workbook_2:
                print("'{}' and '{}' are the same".format(args.data_file_1, args.data_file_2))
            else:
                print("'{}' and '{}' differ".format(args.data_file_1, args.data_file_2))
                if args.differences:
                    print(workbook_1.difference(workbook_2))


class Migrate(cement.App):
    """ Generic command line application """

    class Meta:
        label = 'migrate'
        base_controller = 'base'
        # call sys.exit() on close
        close_on_exit = True


data_repo_migration_controllers = [
    CementControllers.AutomatedMigrationConfigController,
    CementControllers.MigrateController,
    CementControllers.MigrateFileController
    # use wc_lang's DifferenceController instead of CompareFilesController
]


class DataRepoMigrate(Migrate):
    """ Migrate command line application for data repositories """

    class Meta(Migrate.Meta):
        handlers = data_repo_migration_controllers


schema_repo_migration_controllers = [
    CementControllers.SchemaChangesTemplateController
]


class SchemaRepoMigrate(Migrate):
    """ Migrate command line application for schema repositories """

    class Meta(Migrate.Meta):
        handlers = schema_repo_migration_controllers


def generic_main(app_type, test_argv):   # pragma: no cover
    """ Generic main

    Args:
        app_type (:obj:`type`): the type of `cement.App` to use
        test_argv (:obj:`list`): command line arguments for testing
    """
    test_argv_kwargs = {}
    if test_argv:
        test_argv_kwargs = dict(argv=test_argv)
    with app_type(**test_argv_kwargs) as app:
        app.args.add_argument('-v', '--version', action='version',
            version=obj_model.__version__,
            help='version of the migration software')
        try:
            app.run()
        except MigratorError as e:
            print("MigratorError > {}".format(e.args[0]))
            app.exit_code = 1

            if app.debug is True:
                import traceback
                traceback.print_exc()


def data_repo_main(test_argv=None):
    """ main for use by data repositories """
    generic_main(DataRepoMigrate, test_argv=test_argv)


def schema_repo_main(test_argv=None):
    """ main for use by schema repositories """
    generic_main(SchemaRepoMigrate, test_argv=test_argv)


class VirtualEnvUtil(object):   # pragma: no cover
    # INCOMPLETE: started and not finished; not tested
    # NEEDS:
    # from virtualenvapi.manage import VirtualEnvironment
    # import virtualenvapi
    """ Support creation, use and distruction of virtual environments for Python packages

    Will be used to allow different schema versions depend on different package versions

    Attributes:
        name (:obj:`str`): name of the `VirtualEnvUtil`
    """

    def __init__(self, name, dir=None):
        """ Initialize a `VirtualEnvUtil`

        Args:
            name (:obj:`str`): name for the `VirtualEnvUtil`
            dir (:obj:`str`, optional): a directory to hold the `VirtualEnvUtil`
        """
        if re.search(r'\s', name):
            raise ValueError("name '{}' may not contain whitespace".format(name))
        self.name = name
        if dir is None:
            dir = tempfile.mkdtemp()
        self.virtualenv_dir = os.path.join(dir, name)
        if os.path.isdir(self.virtualenv_dir):
            raise ValueError("directory '{}' already exists".format(self.virtualenv_dir))
        os.mkdir(self.virtualenv_dir)
        self.env = VirtualEnvironment(self.virtualenv_dir)

    def is_installed(self, pip_spec):
        return self.env.is_installed(pip_spec)

    def install_from_pip_spec(self, pip_spec):
        """ Install a package from a `pip` specification

        Args:
            pip_spec (:obj:`str`): a `pip` specification for a package to load

        Raises:
            :obj:`ValueError`: if the package described by `pip_spec` cannot be installed
        """
        try:
            self.env.install(pip_spec)
        except virtualenvapi.exceptions.PackageInstallationException as e:
            print('returncode', e.returncode)
            print('output', e.output)
            print('package', e.package)

    def activate(self):
        """ Use this `VirtualEnvUtil`
        """
        # put the env on sys.path
        pass

    def deactivate(self):
        """ Stop using this `VirtualEnvUtil`
        """
        # remove this env from sys.path
        pass

    def destroy(self):
        """ Destroy this `VirtualEnvUtil`

        Distruction deletes the directory storing the `VirtualEnvUtil`
        """
        shutil.rmtree(self.virtualenv_dir)

    def destroyed(self):
        """ Test whether this `VirtualEnvUtil` has been destroyed
        """
        return not os.path.isdir(self.virtualenv_dir)
