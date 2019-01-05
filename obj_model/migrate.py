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
from wc_utils.util.list import det_find_dupes, det_count_elements
from obj_model.expression import ParsedExpression, ObjModelTokenCodes


# todo next: test big wc_lang model, deal with implicit Model attributes
# todo: test_migrate_from_config and test if self.seq_of_renamed_models
# todo next: more coverage
# todo next: address perf. problem with wc_lang migration, if they persist
# todo next: test OneToManyAttribute
# todo next: medium: use to migrate xlsx files in wc_sim to new wc_lang
# todo next: medium: remove as much code as possible from tests/fixtures/migrate/wc_lang

# todo next: move remaining todos to GitHub issues
# todo next: medium: clean up naming: old models, existing, migrated models, new models, source models, dest models
# todo: have obj_model support required attributes, which have non-default values; e.g.
# turn off coverage during unittest setUp, if possible
# the Model attr in models in a wc_lang model should be required
# todo: separately specified default value for attribute
# todo: obtain sort order of sheets in existing model file and replicate in migrated model file
# todo: confirm this works for json, etc.
# todo: test sym links in Migrator._normalize_filename
# todo: make the yaml config files more convenient: map filenames to the directory containing the config file;
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
        old_model_defs_file (:obj:`str`): file name of Python file containing old model definitions
        new_model_defs_file (:obj:`str`): file name of Python file containing new model definitions
        old_model_defs_path (:obj:`str`): pathname of Python file containing old model definitions
        new_model_defs_path (:obj:`str`): pathname of Python file containing new model definitions
        modules (:obj:`dict`): modules being used for migration, indexed by full pathname
        old_model_defs (:obj:`dict`): `obj_model.Model` definitions of the old models, keyed by name
        new_model_defs (:obj:`dict`): `obj_model.Model` definitions of the new models, keyed by name
        deleted_models (:obj:`set`): model types defined in the old models but not the new models
        renamed_models (:obj:`list` of :obj:`tuple`): model types renamed from the existing to the migrated schema
        models_map (:obj:`dict`): map from existing model names to migrated model names
        renamed_attributes (:obj:`list` of :obj:`tuple`): attribute names renamed from the existing to
            the migrated schema
        renamed_attributes_map (:obj:`dict`): map of attribute names renamed from the existing to the migrated schema
        _migrated_copy_attr_name (:obj:`str`): attribute name used to point old models to corresponding
            new models; not used in any old model definitions
        transformations (:obj:`dict`): map of transformation types in `SUPPORTED_TRANSFORMATIONS` to callables
    """

    # default suffix for a migrated model file
    MIGRATE_SUFFIX = '_migrated'

    # modules being used for migration, indexed by full pathname
    # Migrator does not need or support packages
    modules = {}

    # prefix of attribute name used to connect old and new models during migration
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

    def __init__(self, old_model_defs_file=None, new_model_defs_file=None, renamed_models=None,
        renamed_attributes=None, transformations=None):
        """ Construct a Migrator

        Args:
            old_model_defs_file (:obj:`str`, optional): path of a file containing old Model definitions
            new_model_defs_file (:obj:`str`, optional): path of a file containing new Model definitions;
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
        self.old_model_defs_file = old_model_defs_file
        self.new_model_defs_file = new_model_defs_file
        self.renamed_models = [] if renamed_models is None else renamed_models
        self.renamed_attributes = [] if renamed_attributes is None else renamed_attributes
        self.transformations = transformations
        self.old_model_defs_path = None
        self.new_model_defs_path = None

    def load_defs_from_files(self):
        """ Initialize a `Migrator`s model definitions from files

        Distinct from `prepare` so most of `Migrator` can be tested with models defined in code
        """
        if self.old_model_defs_file:
            self.old_model_defs_path = self._normalize_filename(self.old_model_defs_file)
            self._valid_python_path(self.old_model_defs_path)
            self.old_model_defs = self._get_model_defs(self._load_model_defs_file(self.old_model_defs_path))
        if self.new_model_defs_file:
            self.new_model_defs_path = self._normalize_filename(self.new_model_defs_file)
            self._valid_python_path(self.new_model_defs_path)
            self.new_model_defs = self._get_model_defs(self._load_model_defs_file(self.new_model_defs_path))
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
        for old_model_def in self.old_model_defs.values():
            for attr in old_model_def.Meta.attributes.values():
                max_len = max(max_len, len(attr.name))
        return "{}{}".format(Migrator.MIGRATED_COPY_ATTR_PREFIX,
            '_' * (max_len + 1 - len(Migrator.MIGRATED_COPY_ATTR_PREFIX)))

    @staticmethod
    def _normalize_filename(filename):
        """ Normalize a filename to its fully expanded, real, absolute path

        Args:
            filename (:obj:`str`): a filename

        Returns:
            :obj:`str`: `filename`'s fully expanded, real, absolute path
        """
        filename = os.path.expanduser(filename)
        filename = os.path.expandvars(filename)
        filename = os.path.realpath(filename)
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
            if existing_model not in self.old_model_defs:
                errors.append("'{}' in renamed models not an existing model".format(existing_model))
            if migrated_model not in self.new_model_defs:
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
        for existing_model in self.old_model_defs:
            if existing_model not in self.models_map and existing_model in self.new_model_defs:
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
            if existing_model not in self.old_model_defs or \
                existing_attr not in self.old_model_defs[existing_model].Meta.attributes:
                errors.append("'{}.{}' in renamed attributes not an existing model.attribute".format(
                    existing_model, existing_attr))
            if migrated_model not in self.new_model_defs or \
                migrated_attr not in self.new_model_defs[migrated_model].Meta.attributes:
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
            if existing_attribute in self.new_model_defs[migrated_class].Meta.attributes:
                return (migrated_class, self.new_model_defs[migrated_class].Meta.attributes[existing_attribute].name)

        return (None, None)

    def prepare(self):
        """ Prepare for migration

        Raises:
            :obj:`MigratorError`: if renamings are not valid, or
                inconsistencies exist between corresponding old and migrated classes
        """

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
        self.deleted_models = set(self.old_model_defs).difference(used_models)

        # check that corresponding models in old and new are consistent
        inconsistencies = []
        for existing_model, migrated_model in self.models_map.items():
            inconsistencies.extend(self._get_inconsistencies(existing_model, migrated_model))
        if inconsistencies:
            raise MigratorError('\n'.join(inconsistencies))

        # get attribute name not used in old model definitions so that old models can point to new models
        self._migrated_copy_attr_name = self._get_migrated_copy_attr_name()

    def _get_inconsistencies(self, old_model, new_model):
        """ Detect inconsistencies between `old_model` and `new_model` model classes

        Detect inconsistencies between `old_model` and `new_model`. Inconsistencies arise if the loaded `old_model`
        or `new_model` definitions are not consistent with their model or attribute renaming specifications
        or with each other.

        Args:
            old_model (:obj:`str`): name of an old model class
            new_model (:obj:`str`): name of the corresponding new model class

        Returns:
            :obj:`list`: inconsistencies between old_model_cls and new_model_cls; an empty list if
                no inconsistencies exist
        """
        inconsistencies = []

        # constraint: old_model and new_model must be available in their respective model definitions
        path = "'{}'".format(self.old_model_defs_path) if self.old_model_defs_path else 'old models definitions'
        if old_model not in self.old_model_defs:
            inconsistencies.append("old model {} not found in {}".format(old_model, path))
        path = "'{}'".format(self.new_model_defs_path) if self.new_model_defs_path else 'new models definitions'
        if new_model not in self.new_model_defs:
            inconsistencies.append("new model {} corresponding to old model {} not found in {}".format(
                new_model, old_model, path))
        if inconsistencies:
            # return these inconsistencies because they prevent checks below from running accurately
            return inconsistencies

        # constraint: old_model and new_model must be have the same type, which will be obj_model.core.ModelMeta
        old_model_cls = self.old_model_defs[old_model]
        new_model_cls = self.new_model_defs[new_model]
        if type(old_model_cls) != type(new_model_cls):
            inconsistencies.append("type of old model '{}' doesn't equal type of new model '{}'".format(
                type(old_model_cls).__name__, type(new_model_cls).__name__))

        # constraint: names of old_model and new_model classes must match their names in the models map
        if old_model_cls.__name__ != old_model:
            inconsistencies.append("name of old model class '{}' not equal to its name in the models map '{}'".format(
                old_model_cls.__name__, old_model))
        if new_model_cls.__name__ != new_model:
            inconsistencies.append("name of new model class '{}' not equal to its name in the models map '{}'".format(
                new_model_cls.__name__, new_model))
        new_model_cls = self.new_model_defs[new_model]
        expected_migrated_model_name = self.models_map[old_model]
        if new_model_cls.__name__ != expected_migrated_model_name:
            inconsistencies.append("models map says '{}' migrates to '{}', but _get_inconsistencies parameters "
                "say '{}' migrates to '{}'".format(old_model, expected_migrated_model_name, old_model,
                    new_model))
        if inconsistencies:
            # given these inconsistencies the checks below would not be informative
            return inconsistencies

        # constraint: the types of attributes in old_model and new_model classes must match
        for old_attr_name, old_attr in old_model_cls.Meta.attributes.items():
            migrated_class, migrated_attr = self._get_mapped_attribute(old_model, old_attr_name)
            # skip if the attr isn't migrated
            if migrated_attr:
                new_attr = new_model_cls.Meta.attributes[migrated_attr]
                if type(old_attr).__name__ != type(new_attr).__name__:
                    inconsistencies.append("existing attribute {}.{} type {} differs from its "
                        "migrated attribute {}.{} type {}".format(old_model, old_attr_name,
                        type(old_attr).__name__, migrated_class, migrated_attr, type(new_attr).__name__))
        if inconsistencies:
            # given these inconsistencies the checks below would not be informative
            return inconsistencies

        # constraint: related names and types of related attributes in old_model and new_model classes must match
        related_attrs_to_check = ['related_name', 'primary_class', 'related_class']
        for old_attr_name, old_attr in old_model_cls.Meta.attributes.items():
            migrated_class, migrated_attr = self._get_mapped_attribute(old_model, old_attr_name)
            if migrated_attr and isinstance(old_attr, obj_model.RelatedAttribute):
                new_attr = new_model_cls.Meta.attributes[migrated_attr]
                for rel_attr in related_attrs_to_check:
                    old_rel_attr = getattr(old_attr, rel_attr)
                    new_rel_attr = getattr(new_attr, rel_attr)
                    if isinstance(old_rel_attr, str) and isinstance(new_rel_attr, str):
                        if old_rel_attr != new_rel_attr:
                            inconsistencies.append("{}.{}.{} is '{}', which differs from the migrated value "
                                "of {}.{}.{}, which is '{}'".format(old_model, old_attr_name, rel_attr,
                                old_rel_attr, migrated_class, migrated_attr, rel_attr, new_rel_attr))
                    else:
                        # the attributes are models
                        old_rel_attr_name = old_rel_attr.__name__
                        new_rel_attr_name = new_rel_attr.__name__
                        if old_rel_attr_name in self.deleted_models:
                            inconsistencies.append("existing model '{}' is not migrated, "
                                "but is referenced by migrated attribute {}.{}".format(old_rel_attr_name,
                                migrated_class, migrated_attr))
                        else:
                            expected_new_rel_attr = self.models_map[old_rel_attr_name]
                            if new_rel_attr_name != expected_new_rel_attr:
                                inconsistencies.append("{}.{}.{} is '{}', which migrates to '{}', but it "
                                    "differs from {}.{}.{}, which is '{}'".format(
                                    old_model, old_attr_name, rel_attr, old_rel_attr_name, expected_new_rel_attr,
                                    migrated_class, migrated_attr, rel_attr, new_rel_attr_name))
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

        existing_models_migrating = [self.old_model_defs[model_name] for model_name in self.models_map.keys()]

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

        Map the order of existing models to an order for migrated models. The new order can be
        used to sequence worksheets or files in migrated file(s).

        Args:
            model_order (:obj:`list` of `obj_model.core.ModelMeta`:): order of existing models

        Returns:
            :obj:`list` of `obj_model.core.ModelMeta`: migrated models in the same order as
                the corresponding existing models, followed by new models sorted by name
        """

        model_type_map = {}
        for existing_model, migrated_model in self.models_map.items():
            model_type_map[self.old_model_defs[existing_model]] = self.new_model_defs[migrated_model]

        migrated_model_order = []
        for existing_model in model_order:
            try:
                migrated_model_order.append(model_type_map[existing_model])
            except KeyError:
                raise MigratorError("model '{}' not found in the model map".format(
                    existing_model.__name__))

        # append newly created models
        new_model_names = [new_model_name
            for new_model_name in set(self.new_model_defs).difference(self.models_map.values())]
        new_models = [self.new_model_defs[model_name] for model_name in sorted(new_model_names)]
        migrated_model_order.extend(new_models)

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
        root, ext = os.path.splitext(existing_file)
        obj_model_reader = obj_model.io.get_reader(ext)()
        # ignore_sheet_order because models obtained by inspect.getmembers() are returned in name order
        old_models = obj_model_reader.run(existing_file, models=self._get_models_with_worksheets(self.old_model_defs),
            ignore_attribute_order=True, ignore_sheet_order=True, include_all_attributes=False)
        models_read = []
        for models in old_models.values():
            models_read.extend(models)
        return models_read

    def migrate(self, existing_models):
        """ Migrate existing model instances to new schema

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
                save migrated file with new suffix in same directory as source file
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
        obj_model_writer = obj_model.io.get_writer(ext)()
        obj_model_writer.run(migrated_file, migrated_models, models=model_order)
        return migrated_file

    def full_migrate(self, existing_file, migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        """ Migrate data from an existing file to a migrated file

        Args:
            existing_file (:obj:`str`): pathname of file to migrate
            migrated_file (:obj:`str`, optional): pathname of migrated file; if not provided,
                save migrated file with new suffix in same directory as existing file
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
        for inconsistency in self._validate_models(existing_models):
            warn(inconsistency)
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

    def _validate_model(self, old_model, old_model_def):
        """ Validate a model instance against its definition

        Args:
            old_model (:obj:`obj_model.Model`): the old model
            old_model_def (:obj:`obj_model.core.ModelMeta`): type of the old model

        Returns:
            :obj:`list`: inconsistencies between `old_model` and `old_model_def`; an empty list if
                no inconsistencies exist
        """
        inconsistencies = []

        # are attributes in old_model_def missing or uninitialized in old_model
        for attr_name, attr in old_model_def.Meta.attributes.items():
            if not hasattr(old_model, attr_name) or \
                getattr(old_model, attr_name) is attr.get_default_cleaned_value():
                inconsistencies.append("instance(s) of old model '{}' lacks '{}' non-default value".format(
                    old_model_def.__name__, attr_name))

        return inconsistencies

    def _validate_models(self, existing_models):
        """ Validate existing model instances against their definitions

        Args:
            existing_models (:obj:`list` of `obj_model.Model`:) the models being migrated

        Returns:
            :obj:`list`: inconsistencies in `existing_models`; an empty list if no inconsistencies exist
        """
        existing_models_dict = {}
        for existing_model in existing_models:
            cls = existing_model.__class__
            if cls not in existing_models_dict:
                existing_models_dict[cls] = []
            existing_models_dict[cls].append(existing_model)
        inconsistencies = []
        for old_model_def, old_models in existing_models_dict.items():
            for old_model in old_models:
                inconsistencies.extend(self._validate_model(old_model, old_model_def))
        counted_inconsistencies = []
        for inconsistency, count in det_count_elements(inconsistencies):
            counted_inconsistencies.append("{} {}".format(count, inconsistency))
        return counted_inconsistencies

    def _migrate_model(self, old_model, old_model_def, new_model_def):
        """ Migrate a model instance's non-related attributes

        Args:
            old_model (:obj:`obj_model.Model`): the old model
            old_model_def (:obj:`obj_model.core.ModelMeta`): type of the old model
            new_model_def (:obj:`obj_model.core.ModelMeta`): type of the new model

        Returns:
            :obj:`obj_model.Model`: a `new_model_def` instance migrated from `old_model`
        """
        new_model = new_model_def()

        # copy non-Related attributes from old_model to new_model
        for attr in old_model_def.Meta.attributes.values():
            val = getattr(old_model, attr.name)

            # skip attributes that do not get migrated to new_model_def
            _, migrated_attr = self._get_mapped_attribute(old_model_def, attr)
            if migrated_attr is None:
                continue

            if not isinstance(attr, obj_model.RelatedAttribute):
                if val is None:
                    copy_val = val
                elif isinstance(val, (string_types, bool, integer_types, float, Enum, )):
                    copy_val = val
                else:
                    copy_val = copy.deepcopy(val)

                setattr(new_model, migrated_attr, copy_val)

        # save a reference to new_model in old_model, which is used by _connect_models()
        setattr(old_model, self._migrated_copy_attr_name, new_model)
        return new_model

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

    def _migrate_analyzed_expr(self, old_model, new_model, new_models):
        """ Run the migration of a model instance's `ParsedExpression` attribute, if it has one

        This must be done after all new models have been created. The migrated `ParsedExpression`
        is assigned to the appropriate attribute in `new_model`.

        Args:
            old_model (:obj:`obj_model.Model`): the old model
            new_model (:obj:`obj_model.Model`): the corresponding new model
            new_models (:obj:`dict`): dict of Models; maps new model type to a dict mapping
                new model ids to new model instances

        Raises:
            :obj:`MigratorError`: if the `ParsedExpression` in `old_model` cannot be migrated
        """
        if hasattr(old_model, self.PARSED_EXPR):
            existing_analyzed_expr = getattr(old_model, self.PARSED_EXPR)
            new_attribute = self.PARSED_EXPR
            new_expression = self._migrate_expression(existing_analyzed_expr)
            new_given_model_types = []
            for existing_model_type in existing_analyzed_expr.related_objects.keys():
                new_given_model_types.append(self.new_model_defs[self.models_map[existing_model_type.__name__]])
            parsed_expr = ParsedExpression(new_model.__class__, new_attribute, new_expression, new_models)
            _, _, errors = parsed_expr.tokenize()
            if errors:
                raise MigratorError('\n'.join(errors))
            setattr(new_model, self.PARSED_EXPR, parsed_expr)

    def _migrate_all_analyzed_exprs(self, all_models):
        """ Migrate all model instances' `ParsedExpression`s

        This must be done after all new models have been created.

        Args:
            all_models (:obj:`list` of `tuple`): pairs of corresponding old and new model instances

        Raises:
            :obj:`MigratorError`: if multiple instances of a model type have the same id
        """
        errors = []
        new_models = {}
        for _, new_model in all_models:
            if new_model.__class__ not in new_models:
                new_models[new_model.__class__] = {}
            # ignore models that do not have an 'id' attribute
            if hasattr(new_model, 'id'):
                id = new_model.id
                if id in new_models[new_model.__class__]:
                    errors.append("model type '{}' has duplicated id: '{}' ".format(
                        new_model.__class__.__name__, id))
                new_models[new_model.__class__][id] = new_model
        if errors:
            raise MigratorError('\n'.join(errors))

        for old_model, new_model in all_models:
            self._migrate_analyzed_expr(old_model, new_model, new_models)

    def _deep_migrate(self, old_models):
        """ Migrate all model instances from old to new model definitions

        Supports:
            * delete attributes from old schema
            * add attributes in new schema
            * add model definitions in new schema
            * models with expressions
        Assumes that otherwise the schemas are identical

        Args:
            old_models (:obj:`list` of `obj_model.Model`): the old models

        Returns:
            :obj:`list`: list of (old model, corresponding new model) pairs
        """
        old_schema = self.old_model_defs
        new_schema = self.new_model_defs

        all_models = []
        for old_model in old_models:
            existing_class_name = old_model.__class__.__name__

            # do not migrate model instancess whose classes are not in the migrated schema
            if existing_class_name in self.deleted_models:
                continue

            migrated_class_name = self.models_map[existing_class_name]
            new_model = self._migrate_model(old_model, old_schema[existing_class_name],
                new_schema[migrated_class_name])
            all_models.append((old_model, new_model))
        self._migrate_all_analyzed_exprs(all_models)
        return all_models

    def _connect_models(self, all_models):
        """ Connect migrated model instances

        Migrate `obj_model.RelatedAttribute` connections among old models to new models

        Args:
            all_models (:obj:`list` of `tuple`): pairs of corresponding old and new model instances
        """
        for old_model, new_model in all_models:
            old_model_cls = old_model.__class__
            for attr_name, attr in old_model_cls.Meta.attributes.items():

                # skip attributes that are not in new_model_def
                _, migrated_attr = self._get_mapped_attribute(old_model_cls, attr)
                if migrated_attr is None:
                    continue

                if isinstance(attr, obj_model.RelatedAttribute):
                    val = getattr(old_model, attr_name)
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

                    setattr(new_model, migrated_attr, migrated_val)

        for old_model, new_model in all_models:
            # delete the reference to new_model in old_model
            delattr(old_model, self._migrated_copy_attr_name)

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
        rv = []
        scalar_attrs = ['old_model_defs_file', 'new_model_defs_file', 'old_model_defs_path',
            'new_model_defs_path', 'deleted_models', '_migrated_copy_attr_name']
        collections_attrs = ['old_model_defs', 'new_model_defs', 'renamed_models', 'models_map',
            'renamed_attributes', 'renamed_attributes_map']
        for attr in scalar_attrs:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                rv.append("{}: {}".format(attr, getattr(self, attr)))
        for attr in collections_attrs:
            if hasattr(self, attr):
                rv.append("{}:\n{}".format(attr, pformat(getattr(self, attr))))
        return '\n'.join(rv)


class MigrationDesc(object):
    """ Description of a sequence of migrations from an existing file

    Attributes:
        _required_attrs (:obj:`list` of :obj:`str`): required attributes in a `MigrationDesc`
        _renaming_lists (:obj:`list` of :obj:`str`): model and attribute renaming lists in a `MigrationDesc`
        _allowed_attrs (:obj:`list` of :obj:`str`): attributes allowed in a `MigrationDesc`
        name (:obj:`str`): name for this `MigrationDesc`
        existing_file (:obj:`str`, optional): existing file to migrate from
        model_defs_files (:obj:`list` of :obj:`str`, optional): list of Python files containing model
            definitions for each state in a sequence of migrations
        seq_of_renamed_models (:obj:`list` of :obj:`list`, optional): list of renamed models for use
            by a `Migrator` for each migration in a sequence of migrations
        seq_of_renamed_attributes (:obj:`list` of :obj:`list`, optional): list of renamed attributes
            for use by a `Migrator` for each migration in a sequence of migrations
        migrated_file (:obj:`str`, optional): destination file
        migrate_suffix (:obj:`str`, optional): suffix added to destination file name, before the file type suffix
        migrate_in_place (:obj:`bool`, optional): whether to migrate `existing_file` in place
    """

    _required_attrs = ['name', 'existing_file', 'model_defs_files']
    _renaming_lists = ['seq_of_renamed_models', 'seq_of_renamed_attributes']
    _allowed_attrs = _required_attrs + _renaming_lists + ['migrated_file', 'migrate_suffix', 'migrate_in_place']

    def __init__(self, name, existing_file=None, model_defs_files=None, seq_of_renamed_models=None,
        seq_of_renamed_attributes=None, migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        self.name = name
        self.existing_file = existing_file
        self.model_defs_files = model_defs_files
        self.seq_of_renamed_models = seq_of_renamed_models
        self.seq_of_renamed_attributes = seq_of_renamed_attributes
        self.migrated_file = migrated_file
        self.migrate_suffix = migrate_suffix
        self.migrate_in_place = migrate_in_place

    def validate(self):
        """ Validate the attributes and relative cardinality of a migration description
        """
        errors = []
        members = inspect.getmembers(self, lambda a: not(inspect.isclass(a) or inspect.ismethod(a)))
        members = [attr for attr, value in members if not attr.startswith('_')]
        extra_attrs = set(members).difference(self._allowed_attrs)
        if extra_attrs:
            errors.append("disallowed attribute(s) found: {}".format(extra_attrs))

        for required_attr in self._required_attrs:
            if getattr(self, required_attr) is None:
                errors.append("missing required attribute '{}'".format(required_attr))
        if errors:
            return errors

        if len(self.model_defs_files) < 2:
            return ["model_defs_files must contain at least 2 model definitions, but it has only {}".format(
                len(self.model_defs_files))]

        for renaming_list in self._renaming_lists:
            if getattr(self, renaming_list) is not None:
                if len(getattr(self, renaming_list)) != len(self.model_defs_files) - 1:
                    errors.append("model_defs_files specifies {} migration(s), but {} contains {} mapping(s)".format(
                        len(self.model_defs_files) - 1, renaming_list, len(getattr(self, renaming_list))))

        # print('self.seq_of_renamed_models')
        # pprint(self.seq_of_renamed_models)
        if self.seq_of_renamed_models:
            required_structure = "seq_of_renamed_models must be a list of lists of pairs of strs"
            try:
                for renaming in self.seq_of_renamed_models:
                    # constraint: renaming must be an iterator over pairs of str
                    for pair in renaming:
                        if len(pair) != 2 or not isinstance(pair[0], str) or not isinstance(pair[1], str):
                            errors.append()
            except TypeError as e:
                errors.append(required_structure + ", but examinining it generates a '{}' error".format(str(e)))

        # print('self.seq_of_renamed_attributes')
        # pprint(self.seq_of_renamed_attributes)
        if self.seq_of_renamed_attributes:
            required_structure = "seq_of_renamed_attributes must be a list of lists of pairs of pairs of strs"
            try:
                for renamings in self.seq_of_renamed_attributes:
                    # constraint: renamings must be a list of pairs of pairs of str
                    for attribute_renaming in renamings:
                        for attr_spec in attribute_renaming:
                            if len(attr_spec) != 2 or not isinstance(attr_spec[0], str) or \
                                not isinstance(attr_spec[1], str):
                                errors.append(required_structure)
            except TypeError as e:
                errors.append(required_structure + ", but examinining it generates a '{}' error".format(str(e)))

        if not errors:
            self.standardize()
        return errors

    def standardize(self):
        """ Standardize
        """
        # convert [model, attr] pairs in seq_of_renamed_attributes into tuples; needed for hashing
        if self.seq_of_renamed_attributes:
            new_renamed_attributes = []
            for renamed_attrs_in_a_migration in self.seq_of_renamed_attributes:
                if renamed_attrs_in_a_migration is None:
                    new_renamed_attributes.append(None)
                    continue
                a_migration_renaming = []
                for existing, migrated in renamed_attrs_in_a_migration:
                    a_migration_renaming.append((tuple(existing), tuple(migrated)))
                new_renamed_attributes.append(a_migration_renaming)
            self.seq_of_renamed_attributes = new_renamed_attributes

        # if a renaming_list isn't provided, replace it with a list of None indicating no renaming
        empty_per_migration_list = [None]*(len(self.model_defs_files) - 1)
        for renaming_list in self._renaming_lists:
            if getattr(self, renaming_list) is None:
                setattr(self, renaming_list, empty_per_migration_list)

    def get_kwargs(self):
        # get kwargs for optional args
        optional_args = ['existing_file', 'model_defs_files', 'seq_of_renamed_models', 'seq_of_renamed_attributes',
            'migrated_file', 'migrate_suffix', 'migrate_in_place']
        kwargs = {}
        for arg in optional_args:
            kwargs[arg] = getattr(self, arg)
        return kwargs

    def __str__(self):
        rv = []
        for attr in self._allowed_attrs:
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
            :obj:`tuple` of :obj:`dict`, :obj:`dict`, :obj:`str`: existing models, migrated models,
                name of migrated file

        Raises:
            :obj:`MigratorError`: if `model_defs_files`, `renamed_models`, and `seq_of_renamed_attributes`
                are not consistent with each other;
        """
        validate_errors = migration_desc.validate()
        if validate_errors:
            raise MigratorError('\n'.join(validate_errors))

        md = migration_desc
        num_migrations = len(md.model_defs_files) - 1
        for i in range(len(md.model_defs_files)):
            # create Migrator for each pair of schemas
            migrator = Migrator(md.model_defs_files[i], md.model_defs_files[i+1], md.seq_of_renamed_models[i],
                md.seq_of_renamed_attributes[i])
            migrator.load_defs_from_files().prepare()
            # migrate in memory until the last migration
            if i == 0:
                models = existing_models = migrator.read_existing_model(md.existing_file)
                existing_model_order = migrator._get_existing_model_order(md.existing_file)
                model_order = existing_model_order
            for inconsistency in migrator._validate_models(existing_models):
                warn(inconsistency)
            models = migrator.migrate(models)
            model_order = migrator._migrate_model_order(model_order)
            if i == num_migrations - 1:
                # done migrating, write to file
                migrated_file = migrator.write_migrated_file(models, model_order, md.existing_file,
                    migrated_file=md.migrated_file, migrate_suffix=md.migrate_suffix,
                    migrate_in_place=md.migrate_in_place)
                break
        return existing_models, models, migrated_file

    @staticmethod
    def get_migrations_config(migrations_config_file):
        """ Read and initially validate migrations configuration file

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`list` of :obj:`MigrationDesc`: migration descriptions

        Raises:
            :obj:`MigratorError`: if `migrations_config_file` cannot be read, or the migration descriptions in
                `migrations_config_file` are not valid
        """
        try:
            fd = open(migrations_config_file, 'r')
        except FileNotFoundError as e:
            raise MigratorError("could not read migration config file: '{}'".format(migrations_config_file))
        config = yaml.load(fd)

        # parse the config
        migration_descs = {}
        for migration_name, migration_desc in config.items():
            migration_desc_obj = MigrationDesc(migration_name)
            for param, value in migration_desc.items():
                setattr(migration_desc_obj, param, value)
            migration_descs[migration_name] = migration_desc_obj
        migration_errors = []
        for migration_name, migration_desc_obj in migration_descs.items():
            validate_errors = migration_desc_obj.validate()
            if validate_errors:
                migration_errors.extend(validate_errors)
        if migration_errors:
            raise MigratorError('\n'.join(migration_errors))
        return migration_descs

    @staticmethod
    def migrate_from_desc(migration_desc):
        """ Perform a migration described in a `MigrationDesc`

        Args:
            migration_desc (:obj:`MigrationDesc`): a migration description

        Returns:
            :obj:`str`: migrated filename
        """
        _, _, migrated_filename = MigrationController.migrate_over_schema_sequence(migration_desc)
        return migrated_filename

    @staticmethod
    def migrate_from_config(migrations_config_file):
        """ Perform the migrations specified in a config file

        Args:
            migrations_config_file (:obj:`str`): migrations specified in a YAML file

        Returns:
            :obj:`list` of :obj:`str`: migrated filenames
        """
        migration_descs = MigrationController.get_migrations_config(migrations_config_file)
        results = []
        for migration_desc in migration_descs.values():
            results.append(MigrationController.migrate_from_desc(migration_desc))
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
            description="Migrate model file(s) from an existing schema to a new one")
        parser.add_argument('existing_model_definitions',
            help="Python file containing existing obj_model.Model definitions")
        parser.add_argument('new_model_definitions',
            help="Python file containing new obj_model.Model definitions")
        parser.add_argument('files', nargs='+',
            help="Files(s) to migrate from existing to new obj_model.Model definitions; "
            "new files will be written with a '_migrate' suffix")
        args = parser.parse_args(cli_args)
        return args

    @staticmethod
    def main(args):
        migrator = Migrator(args.existing_model_definitions, args.new_model_definitions)
        migrator.load_defs_from_files().prepare()
        return migrator.run(args.files)

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
