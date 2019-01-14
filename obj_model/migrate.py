""" Support schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""
import os
import sys
import argparse
import importlib
import inspect
import copy
import yaml
from six import integer_types, string_types
from enum import Enum
from warnings import warn
from pprint import pprint, pformat

import obj_model
from obj_model import TabularOrientation
from obj_model.io import WorkbookReader, IoWarning
import wc_utils
from wc_utils.util.list import det_find_dupes, det_count_elements, dict_by_class
from obj_model.expression import ParsedExpression, ObjModelTokenCodes


# todo next: medium: use to migrate xlsx files in wc_sim to new wc_lang
'''
1: identify all xlsx files, and the wc_lang commit that they use
2: migrate them
'''
# todo next: documentation
# todo next: remove '/'s in test_migrate.py so it's OS portable
# todo next: final bit of coverage
# todo next: test OneToManyAttribute
# todo next: enable wc_lang migration in RunMigration
# todo: prepare lab meeting
# use dict in wc_utils dup removal

# todo next: move remaining todos to GitHub issues
# todo: move generate_wc_lang_migrator() to wc_lang
# turn off coverage during unittest setUp, if possible
# todo: separately specified default value for attribute
# todo: obtain sort order of sheets in existing model file and replicate in migrated model file
# todo: confirm this works for json, etc.
# todo: test sym links in Migrator._normalize_filename
# provide a well-documented example;
# todo: refactor testing into individual tests for read_existing_model, migrate, and write_migrated_file
# todo: use PARSED_EXPR everywhere applicable
# todo: support high-level, WC wc_lang specific migration of a repo
#       use case:
#           1 change wc_lang/core.py
#           2 in some repo migrate all model files over multiple wc_lang versions to the new version
#       implementation:
#           each WC repo that has model files maintains a migrate.yml config file with: list of model files to migrate; migration options
#           wc_lang contains migration_transformations.py, which provides all arbitrary transformations
#           "migrate_repo repo" uses repo's migrate.yml and migration_transformations.py to migrate all model files in repo
# todo: use Model.revision to label git commit of wc_lang and automatically migrate models to current schema
# and to report inconsistency between a schema and model file
# todo: support generic type conversion of migrated data by plug-in functions provided by a users

class MigratorError(Exception):
    """ Exception raised for errors in obj_model.migrate

    Attributes:
        message (:obj:`str`): the exception's message
    """
    def __init__(self, message=None):
        super().__init__(message)


class Migrator(object):
    """ Support schema migration

    Attributes:
        existing_defs_file (:obj:`str`): file name of Python file containing existing model definitions
        migrated_defs_file (:obj:`str`): file name of Python file containing migrated model definitions
        existing_defs_path (:obj:`str`): pathname of Python file containing existing model definitions
        migrated_defs_path (:obj:`str`): pathname of Python file containing migrated model definitions
        modules (:obj:`dict`): modules being used for migration, indexed by full pathname
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

    SCALAR_ATTRS = ['existing_defs_file', 'migrated_defs_file', 'existing_defs_path',
        'migrated_defs_path', 'deleted_models', '_migrated_copy_attr_name']
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
        self.existing_defs_file = existing_defs_file
        self.migrated_defs_file = migrated_defs_file
        self.renamed_models = [] if renamed_models is None else renamed_models
        self.renamed_attributes = [] if renamed_attributes is None else renamed_attributes
        self.transformations = transformations
        self.existing_defs_path = None
        self.migrated_defs_path = None

    def _load_defs_from_files(self):
        """ Initialize a `Migrator`s model definitions from files

        Distinct from `prepare` so most of `Migrator` can be tested with models defined in code
        """
        if self.existing_defs_file:
            self.existing_defs_path = self._normalize_filename(self.existing_defs_file)
            self._valid_python_path(self.existing_defs_path)
            self.existing_defs = self._get_model_defs(self._load_model_defs_file(self.existing_defs_path))
        if self.migrated_defs_file:
            self.migrated_defs_path = self._normalize_filename(self.migrated_defs_file)
            self._valid_python_path(self.migrated_defs_path)
            self.migrated_defs = self._get_model_defs(self._load_model_defs_file(self.migrated_defs_path))
        return self

    @staticmethod
    def _valid_python_path(filename):
        """ Raise error if filename is not a valid Python filename

        Args:
            filename (:obj:`str`): path of a file containing some Model definitions

        Returns:
            :obj:`Module`: the `Module` loaded from a model definitions file

        Raises:
            :obj:`MigratorError`: if `filename` doesn't end in '.py', or basename of `filename` contains
                extra '.'s
        """
        # error if basename doesn't end in '.py' and contain exactly 1 '.'
        root, ext = os.path.splitext(filename)
        if ext != '.py':
            raise MigratorError("'{}' must be Python filename ending in '.py'".format(filename))
        module_name = os.path.basename(root)
        if '.' in module_name:
            raise MigratorError("module name '{}' in '{}' cannot contain a '.'".format(module_name, filename))

    def _load_model_defs_file(self, model_defs_file):
        """ Import a Python file

        Args:
            model_defs_file (:obj:`str`): path of a file containing some Model definitions

        Returns:
            :obj:`Module`: the `Module` loaded from model_defs_file

        Raises:
            :obj:`MigratorError`: if `model_defs_file` cannot be loaded
        """
        # avoid re-loading file containing Model definitions, which would fail with
        # 'cannot use the same related attribute name' error if its Models have related attributes
        if model_defs_file in self.modules:
            return self.modules[model_defs_file]

        root, _ = os.path.splitext(model_defs_file)
        module_name = os.path.basename(root)
        try:
            spec = importlib.util.spec_from_file_location(module_name, model_defs_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.modules[model_defs_file] = module
        except (SyntaxError, ImportError, AttributeError, ValueError) as e:
            raise MigratorError("'{}' cannot be imported and exec'ed: {}".format(model_defs_file, e))
        return module

    @staticmethod
    def _get_model_defs(module):
        """ Obtain the `obj_model.Model`s in a module

        Args:
            module (:obj:`Module`): a `Module` containing `obj_model.Model` definitions

        Returns:
            :obj:`dict`: the Models in a module
        """
        models = {}
        for name, attr in inspect.getmembers(module, inspect.isclass):
            if isinstance(attr, obj_model.core.ModelMeta):
                models[name] = attr
        return models

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
    def _normalize_filename(filename, dir=None):
        """ Normalize a filename to its fully expanded, real, absolute path

        Expand `filename` by interpreting a user’s home directory, environment variables, and
        normalizing its path. If `filename` is not an absolute path and `dir` is provided then
        return a full path of `filename` in `dir`.

        Args:
            filename (:obj:`str`): a filename
            dir (:obj:`str`, optional): a directory that contains `filename`

        Returns:
            :obj:`str`: `filename`'s fully expanded, absolute path
        """
        filename = os.path.expanduser(filename)
        filename = os.path.expandvars(filename)
        if os.path.isabs(filename):
            return os.path.normpath(filename)
        elif dir:
            return os.path.normpath(os.path.join(dir, filename))
        else:
            return os.path.abspath(filename)

    def _validate_transformations(self):
        """ Validate transformations

        Ensure that self.transformations is a dict of callables

        Returns:
            :obj:`list` of `str`: errors in the renamed models
        """
        errors = []
        if self.transformations:
            if not isinstance(self.transformations, dict):
                return ["transformations should be a dict, but it is a(n) '{}'".format(type(
                    self.transformations).__name__)]
            if not set(self.transformations).issubset(self.SUPPORTED_TRANSFORMATIONS):
                errors.append("names of transformations {} aren't a subset of the supported "
                    "transformations {}".format(set(self.transformations), set(self.SUPPORTED_TRANSFORMATIONS)))
            for transform_name, transformation in self.transformations.items():
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
        self._validate_transformations()

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
        path = "'{}'".format(self.existing_defs_path) if self.existing_defs_path else 'existing models definitions'
        if existing_model not in self.existing_defs:
            inconsistencies.append("existing model {} not found in {}".format(existing_model, path))
        path = "'{}'".format(self.migrated_defs_path) if self.migrated_defs_path else 'migrated models definitions'
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
            warn(msg, IoWarning)

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

        Args:
            existing_file (:obj:`str`): pathname of file to migrate

        Returns:
            :obj:`list` of `obj_model.Model`: the models in `existing_file`
        """
        obj_model_reader = obj_model.io.Reader.get_reader(existing_file)()
        # ignore_sheet_order because models obtained by inspect.getmembers() are returned in name order
        existing_models = obj_model_reader.run(existing_file, models=self._get_models_with_worksheets(self.existing_defs),
            ignore_attribute_order=True, ignore_sheet_order=True, include_all_attributes=False)
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

    def write_migrated_file(self, migrated_models, model_order, existing_file, migrated_file=None,
        migrate_suffix=None, migrate_in_place=False):
        """ Write migrated models to an external representation

        Args:
            migrated_models (:obj:`list` of `obj_model.Model`:) the migrated models
            model_order (:obj:`list` of `obj_model.core.ModelMeta`:) migrated models in the order
                they should appear in a workbook
            existing_file (:obj:`str`): pathname of file to migrate
            migrated_file (:obj:`str`, optional): pathname of migrated file; if not provided,
                save migrated file with migrated suffix in same directory as source file
            migrate_suffix (:obj:`str`, optional): suffix of automatically created migrated filename;
                default is `Migrator.MIGRATE_SUFFIX`
            migrate_in_place (:obj:`bool`, optional): if set, overwrite `source_file` with the
                migrated file and ignore `migrated_file` and `migrate_suffix`

        Returns:
            :obj:`str`: name of migrated file

        Raises:
            :obj:`MigratorError`: if migrate_in_place is False and writing the migrated file would
                overwrite an existing file
        """
        root, ext = os.path.splitext(existing_file)
        # determine pathname of migrated file
        if migrate_in_place:
            migrated_file = existing_file
        else:
            if migrate_suffix is None:
                migrate_suffix = Migrator.MIGRATE_SUFFIX
            if migrated_file is None:
                migrated_file = os.path.join(os.path.dirname(existing_file),
                    os.path.basename(root) + migrate_suffix + ext)
            if os.path.exists(migrated_file):
                raise MigratorError("migrated file '{}' already exists".format(migrated_file))

        # write migrated models to disk
        obj_model_writer = obj_model.io.Writer.get_writer(existing_file)()
        obj_model_writer.run(migrated_file, migrated_models, models=model_order)
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
        # transformations: PREPARE_EXISTING_MODELS
        if self.transformations and self.PREPARE_EXISTING_MODELS in self.transformations:
            self.transformations[self.PREPARE_EXISTING_MODELS](self, existing_models)
        for count_uninitialized_attrs in self._check_models(existing_models):
            warn(count_uninitialized_attrs)
        migrated_models = self.migrate(existing_models)
        # transformations: MODIFY_MIGRATED_MODELS
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
                uninitialized_attrs.append("instance(s) of existing model '{}' lacks '{}' non-default value".format(
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

        transformations = {Migrator.PREPARE_EXISTING_MODELS:prepare_existing_wc_lang_models}
        return Migrator(**kwargs, transformations=transformations)

    def run(self, files):
        """ Migrate some files

        Args:
            files (:obj:`list`): names of model files to migrate
        """
        migrated_files = []
        for file in files:
            migrated_files.append(self.full_migrate(self._normalize_filename(file)))
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


class MigrationDesc(object):
    """ Description of a sequence of migrations for a list of existing files

    Attributes:
        _required_attrs (:obj:`list` of :obj:`str`): required attributes in a `MigrationDesc`
        _renaming_lists (:obj:`list` of :obj:`str`): model and attribute renaming lists in a `MigrationDesc`
        _allowed_attrs (:obj:`list` of :obj:`str`): attributes allowed in a `MigrationDesc`
        name (:obj:`str`): name for this `MigrationDesc`
        migrator (:obj:`callable`): the Migrator to use for migrations
        existing_files (:obj:`list`: of :obj:`str`, optional): existing files to migrate
        model_defs_files (:obj:`list` of :obj:`str`, optional): list of Python files containing model
            definitions for each state in a sequence of migrations
        seq_of_renamed_models (:obj:`list` of :obj:`list`, optional): list of renamed models for use
            by a `Migrator` for each migration in a sequence of migrations
        seq_of_renamed_attributes (:obj:`list` of :obj:`list`, optional): list of renamed attributes
            for use by a `Migrator` for each migration in a sequence of migrations
        migrated_files (:obj:`list`: of :obj:`str`, optional): migration destination files in 1-to-1
            correspondence with `existing_files`; if not provided, migrated files use a suffix or
            are migrated in place
        migrate_suffix (:obj:`str`, optional): suffix added to destination file name, before the file type suffix
        migrate_in_place (:obj:`bool`, optional): whether to migrate in place
        migrations_config_file (:obj:`str`, optional): path to migrations configuration file, if created
            from a configuration file
    """

    _required_attrs = ['name', 'migrator', 'existing_files', 'model_defs_files']
    _renaming_lists = ['seq_of_renamed_models', 'seq_of_renamed_attributes']
    _allowed_attrs = _required_attrs + _renaming_lists + ['migrated_files', 'migrate_suffix',
        'migrate_in_place', 'migrations_config_file']

    def __init__(self, name, migrator=Migrator, existing_files=None, model_defs_files=None,
        seq_of_renamed_models=None, seq_of_renamed_attributes=None, migrated_files=None, migrate_suffix=None,
        migrate_in_place=False, migrations_config_file=None):
        self.name = name
        self.migrator = migrator
        self.existing_files = existing_files
        self.model_defs_files = model_defs_files
        self.seq_of_renamed_models = seq_of_renamed_models
        self.seq_of_renamed_attributes = seq_of_renamed_attributes
        self.migrated_files = migrated_files
        self.migrate_suffix = migrate_suffix
        self.migrate_in_place = migrate_in_place
        self.migrations_config_file = migrations_config_file

    @classmethod
    def load(cls, migrations_config_file):
        """ Create a list of `MigrationDesc`s from a migrations configuration file

        Validate and standardize the `MigrationDesc`s

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`list` of :obj:`MigrationDesc`: migration descriptions

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read, or the migration descriptions in
                `migrations_config_file` are not valid
        """
        migration_descs = cls.get_migrations_config(migrations_config_file)

        migration_errors = []
        for migration_desc_obj in migration_descs.values():
            migration_errors.extend(migration_desc_obj.validate())
        if migration_errors:
            raise MigratorError('\n'.join(migration_errors))
        for migration_desc_obj in migration_descs.values():
            validate_errors = migration_desc_obj.standardize()
        return migration_descs

    @staticmethod
    def get_migrations_config(migrations_config_file):
        """ Create a `MigrationDesc` from a migrations configuration file

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`list` of :obj:`MigrationDesc`: migration descriptions

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read
        """
        try:
            fd = open(migrations_config_file, 'r')
        except FileNotFoundError as e:
            raise MigratorError("could not read migration config file: '{}'".format(migrations_config_file))
        migrations_config = yaml.load(fd)

        # parse the migrations config
        migration_descs = {}
        for migration_name, migration_desc in migrations_config.items():
            migration_desc_obj = MigrationDesc(migration_name, migrations_config_file=migrations_config_file)
            for param, value in migration_desc.items():
                setattr(migration_desc_obj, param, value)
            migration_descs[migration_name] = migration_desc_obj

        return migration_descs

    def validate(self):
        """ Validate the attributes of a migration description

        Returns:
            :obj:`list` of :obj:`str`: list of errors found
        """
        errors = []
        # check all attributes of self that aren't classes, methods, functions, or private
        members = inspect.getmembers(self, lambda a:
            not(inspect.isclass(a) or inspect.ismethod(a) or inspect.isfunction(a)))
        members = [attr for attr, value in members if not attr.startswith('_')]

        extra_attrs = set(members).difference(self._allowed_attrs)
        if extra_attrs:
            errors.append("disallowed attribute(s) found: {}".format(extra_attrs))

        for required_attr in self._required_attrs:
            if not hasattr(self, required_attr) or getattr(self, required_attr) is None:
                errors.append("missing required attribute '{}'".format(required_attr))
        if errors:
            return errors

        if len(self.model_defs_files) < 2:
            return ["model_defs_files must contain at least 2 model definitions, but it has only {}".format(
                len(self.model_defs_files))]

        for renaming_list in self._renaming_lists:
            if getattr(self, renaming_list) is not None:
                if len(getattr(self, renaming_list)) != len(self.model_defs_files) - 1:
                    errors.append("{} must have 1 mapping for each of the {} migration(s) specified by "
                        "model_defs_files, but it has {}".format(renaming_list,  len(self.model_defs_files) - 1,
                        len(getattr(self, renaming_list))))

        if self.seq_of_renamed_models:
            required_structure = "seq_of_renamed_models must be None, or a list of lists of pairs of strs"
            try:
                for renaming in self.seq_of_renamed_models:
                    if renaming is not None:
                        for pair in renaming:
                            if len(pair) != 2 or not isinstance(pair[0], str) or not isinstance(pair[1], str):
                                errors.append(required_structure)
            except TypeError as e:
                errors.append(required_structure + ", but examining it raises a '{}' error".format(str(e)))

        if self.seq_of_renamed_attributes:
            required_structure = "seq_of_renamed_attributes must be None, or a list of lists of pairs of pairs of strs"
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

        return errors

    @staticmethod
    def _normalize_filenames(filenames, relative_file=None):
        """ Normalize a list of filenames

        Args:
            filenames (:obj:`list` of :obj:`str`): list of filenames
            relative_file (:obj:`str`, optional): file whose directory contains filenames
                that aren't absolute paths

        Returns:
            :obj:`list`: normalized list
        """
        dir = None
        if relative_file:
            dir = os.path.dirname(relative_file)
        return [Migrator._normalize_filename(filename, dir=dir) for filename in filenames]

    def standardize(self):
        """ Standardize the attributes of a `MigrationDesc` that's read from a config file
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

        # if a renaming_list isn't provided, replace it with a list of Nones indicating no renaming
        empty_per_migration_list = [None]*(len(self.model_defs_files) - 1)
        for renaming_list in self._renaming_lists:
            if getattr(self, renaming_list) is None:
                setattr(self, renaming_list, empty_per_migration_list)

        # normalize filenames
        if self.migrations_config_file:
            self.existing_files = self._normalize_filenames(self.existing_files,
                relative_file=self.migrations_config_file)
            self.model_defs_files = self._normalize_filenames(self.model_defs_files,
                relative_file=self.migrations_config_file)
            if self.migrated_files:
                self.migrated_files = self._normalize_filenames(self.migrated_files,
                    relative_file=self.migrations_config_file)

    def get_kwargs(self):
        """ Create a `kwargs` dictionary of a `MigrationDesc`'s optional arguments

        Returns:
            :obj:`dict`: `kwargs` for this `MigrationDesc`'s optional arguments
        """
        optional_args = ['existing_files', 'model_defs_files', 'seq_of_renamed_models', 'seq_of_renamed_attributes',
            'migrated_files', 'migrate_suffix', 'migrate_in_place', 'migrations_config_file']
        kwargs = {}
        for arg in optional_args:
            kwargs[arg] = getattr(self, arg)
        return kwargs

    def __str__(self):
        """ Get str representation

        Returns:
            :obj:`str`: string representation of all allowed attributes in a `MigrationDesc`
        """
        rv = []
        for attr in self._allowed_attrs:
            if attr in self._renaming_lists:
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
    def migrate_over_schema_sequence(migration_desc):
        """ Migrate a model file over a sequence of schemas

        Args:
            migration_desc (:obj:`MigrationDesc`): a migration description

        Returns:
            :obj:`tuple` of :obj:`list`, :obj:`list`: for each migration, its sequence of models and
                its migrated filename

        Raises:
            :obj:`MigratorError`: if `model_defs_files`, `renamed_models`, and `seq_of_renamed_attributes`
                are not consistent with each other;
        """
        validate_errors = migration_desc.validate()
        if validate_errors:
            raise MigratorError('\n'.join(validate_errors))

        md = migration_desc
        # iterate over existing_files & migrated_files
        migrated_files = md.migrated_files if md.migrated_files else [None] * len(md.existing_files)
        all_models, all_migrated_files = [], []
        for existing_file, migrated_file in zip(md.existing_files, migrated_files):
            num_migrations = len(md.model_defs_files) - 1
            # since 0 < num_migrations this loop always executes and branch coverage reports that
            # the 'for' line doesn't jump to return; this cannot be annotated with 'pragma: no cover'
            for i in range(num_migrations):
                # create Migrator for each pair of schemas
                migrator = migration_desc.migrator(existing_defs_file=md.model_defs_files[i],
                    migrated_defs_file=md.model_defs_files[i+1], renamed_models=md.seq_of_renamed_models[i],
                    renamed_attributes=md.seq_of_renamed_attributes[i])
                migrator.prepare()
                # migrate in memory until the last migration
                if i == 0:
                    # the 1st iteration inits `models` from the existing file; iteration n+1 uses `models` set in n
                    models = migrator.read_existing_model(existing_file)
                    all_models.append(models)
                    existing_model_order = migrator._get_existing_model_order(existing_file)
                    model_order = existing_model_order
                for count_uninitialized_attrs in migrator._check_models(models):
                    warn(count_uninitialized_attrs)
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
    def migrate_from_desc(migration_desc):
        """ Perform the migration described in a `MigrationDesc`

        Args:
            migration_desc (:obj:`MigrationDesc`): a migration description

        Returns:
            :obj:`list`: of :obj:`str`: migrated filenames
        """
        _, migrated_filenames = MigrationController.migrate_over_schema_sequence(migration_desc)
        return migrated_filenames

    @staticmethod
    def migrate_from_config(migrations_config_file):
        """ Perform the migrations specified in a config file

        Args:
            migrations_config_file (:obj:`str`): migrations specified in a YAML file

        Returns:
            :obj:`list` of :obj:`tuple`: list of (`MigrationDesc`, migrated filenames) pairs
        """
        migration_descs = MigrationDesc.load(migrations_config_file)
        results = []
        for migration_desc in migration_descs.values():
            results.append((migration_desc, MigrationController.migrate_from_desc(migration_desc)))
        return results


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
        parser.add_argument('existing_model_definitions',
            help="Python file containing existing obj_model.Model definitions")
        parser.add_argument('migrated_model_definitions',
            help="Python file containing migrated obj_model.Model definitions")
        parser.add_argument('files', nargs='+',
            help="Files(s) to migrate from existing to migrated obj_model.Model definitions; "
            "migrated files will be written with a '_migrate' suffix")
        args = parser.parse_args(cli_args)
        return args

    @staticmethod
    def main(args):
        migrator = Migrator(args.existing_model_definitions, args.migrated_model_definitions)
        migrator.prepare()
        return migrator.run(args.files)

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
