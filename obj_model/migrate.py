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
from wc_utils.util.list import det_find_dupes


# local
# todo: test_migrate_from_config
# todo next: large: make work with full wc_lang core.py
# todo: define & use MigrationError
# todo next: medium: clean up naming: old models, existing, migrated models, new models, source models, dest models
# todo next: medium: use to migrate xlsx files in wc_sim to new wc_lang
# Model change
# todo next: medium: add Meta attribute indicator to models (like Species previously) that don't have a worksheet
#   and remove Species hack

# todo next: move remaining todos to GitHub issues
# todo: separately specified default value for attribute
# todo: support arbitrary transformations by an optional function on each migrated instance
# todo: confirm this works for json, etc.
# todo: test sym links in Migrator._normalize_filename
# todo: make the yaml config files more convenient: map filenames to the directory containing the config file;
# provide a well-documented example;
# todo: refactor testing into individual tests for read_existing_model, migrate, and write_migrated_file
# refactor and simplify _get_inconsistencies, and fully test it with test_get_inconsistencies
# todo: support high-level, WC wc_lang specific migration of a repo
#       use case:
#           1 change wc_lang/core.py
#           2 in some repo migrate all model files over multiple wc_lang versions to the new version
#           3 this migration may require arbitrary transformations
#       implementation:
#           each WC repo that has model files maintains a migrate.yml config file with: list of model files to migrate; migration options
#           wc_lang contains migration_transformations.py, which provides all arbitrary transformations
#           "migrate_repo repo" uses repo's migrate.yml and migration_transformations.py to migrate all model files in repo
# todo: use Model.revision to label git commit of wc_lang and automatically migrate models to current schema
# and to report inconsistency between a schema and model file
# todo: support generic type conversion of migrated data by plug-in functions provided by a users
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
    """

    # default suffix for a migrated model file
    MIGRATE_SUFFIX = '_migrated'

    # modules being used for migration, indexed by full pathname
    # Migrator does not need or support packages
    modules = {}

    # prefix of attribute name used to connect old and new models during migration
    MIGRATED_COPY_ATTR_PREFIX = '__migrated_copy'

    def __init__(self, old_model_defs_file, new_model_defs_file, renamed_models=None,
        renamed_attributes=None):
        """ Construct a Migrator

        Args:
            old_model_defs_file (:obj:`str`): path of a file containing old Model definitions
            new_model_defs_file (:obj:`str`): path of a file containing new Model definitions
            renamed_models (:obj:`list` of :obj:`tuple`): model types renamed from the existing to the
                migrated schema; has the form '[('Existing_1', 'Migrated_1'), ..., ('Existing_n', 'Migrated_n')]',
                where `('Existing_i', 'Migrated_i')` indicates that existing model `Existing_i` is
                being renamed into migrated model `Migrated_i`.
            renamed_attributes (:obj:`list` of :obj:`tuple`): attribute names renamed from the existing
                to the migrated schema; a list of tuples of the form
                `(('Existing_Model_i', 'Existing_Attr_x'), ('Migrated_Model_j', 'Migrated_Attr_y'))`,
                which indicates that `Existing_Model_i.Existing_Attr_x` will migrate to
                `Migrated_Model_j.Migrated_Attr_y`.

        Raises:
            :obj:`ValueError`: if one of the defs files is not a python file
        """
        self.old_model_defs_file = old_model_defs_file
        self.new_model_defs_file = new_model_defs_file
        self.renamed_models = [] if renamed_models is None else renamed_models
        self.renamed_attributes = [] if renamed_attributes is None else renamed_attributes

    def initialize(self):
        """ Initialize a Migrator

        Separate from prepare() so most of Migrator can be tested with models defined in code
        """
        self.old_model_defs_path = self._normalize_filename(self.old_model_defs_file)
        self.new_model_defs_path = self._normalize_filename(self.new_model_defs_file)
        self._valid_python_path(self.old_model_defs_path)
        self._valid_python_path(self.new_model_defs_path)
        return self

    @staticmethod
    def _valid_python_path(filename):
        """ Raise error if filename is not a valid Python filename

        Args:
            filename (:obj:`str`): path of a file containing some Model definitions

        Returns:
            :obj:`Module`: the `Module` loaded from model_defs_file

        Raises:
            :obj:`ValueError`: if `filename` doesn't end in '.py', or basename of `filename` contains
                extra '.'s
        """
        # error if basename doesn't end in '.py' and contain exactly 1 '.'
        root, ext = os.path.splitext(filename)
        if ext != '.py':
            raise ValueError("'{}' must be Python filename ending in '.py'".format(filename))
        module_name = os.path.basename(root)
        if '.' in module_name:
            raise ValueError("module name '{}' in '{}' cannot contain a '.'".format(module_name, filename))

    def _load_model_defs_file(self, model_defs_file):
        """ Import a Python file

        Args:
            model_defs_file (:obj:`str`): path of a file containing some Model definitions

        Returns:
            :obj:`Module`: the `Module` loaded from model_defs_file

        Raises:
            :obj:`ValueError`: if `model_defs_file` cannot be loaded
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
            raise ValueError("'{}' cannot be imported and exec'ed: {}".format(model_defs_file, e))
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

    def _get_all_model_defs(self):
        """ Get old and new model defs """
        self.old_model_defs = self._get_model_defs(self._load_model_defs_file(self.old_model_defs_path))
        self.new_model_defs = self._get_model_defs(self._load_model_defs_file(self.new_model_defs_path))

    def _get_migrated_copy_attr_name(self):
        """ Obtain name of attribute used to reference a migrated copy

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
            :obj:`ValueError`: if renamings are not valid, or
                inconsistencies exist between corresponding old and migrated classes
        """
        self._get_all_model_defs()

        # validate that model and attribute rename specifications
        errors = self._validate_renamed_models()
        if errors:
            raise ValueError('\n'.join(errors))
        errors = self._validate_renamed_attrs()
        if errors:
            raise ValueError('\n'.join(errors))

        # find deleted models
        used_models = set([existing_model for existing_model in self.models_map])
        self.deleted_models = set(self.old_model_defs).difference(used_models)

        # check that corresponding models in old and new are consistent
        inconsistencies = []
        for existing_model, migrated_model in self.models_map.items():
            inconsistencies.extend(self._get_inconsistencies(existing_model, migrated_model))
        if inconsistencies:
            raise ValueError('\n'.join(inconsistencies))

        # get attribute name not used in old model definitions so that old models can point to new models
        self._migrated_copy_attr_name = self._get_migrated_copy_attr_name()

    def _get_inconsistencies(self, old_model, new_model):
        """ Detect inconsistencies between old_model and new_model model classes

        Args:
            old_model (:obj:`str`): name of an old model class
            new_model (:obj:`str`): name of the corresponding new model class

        Returns:
            :obj:`list`: inconsistencies between old_model_cls and new_model_cls; an empty list if
                no inconsistencies exist
        """
        inconsistencies = []

        # check existence
        if old_model not in self.old_model_defs:
            inconsistencies.append("old model {} not found in '{}'".format(old_model, self.old_model_defs_path))
        if new_model not in self.new_model_defs:
            inconsistencies.append("new model {} corresponding to old model {} not found in '{}'".format(
                new_model, old_model, self.new_model_defs_path))
        if inconsistencies:
            # return these inconsistencies because they prevent checks below from running accurately
            return inconsistencies

        # check types
        old_model_cls = self.old_model_defs[old_model]
        new_model_cls = self.new_model_defs[new_model]
        if type(old_model_cls) != type(new_model_cls):
            inconsistencies.append("type of old model '{}' doesn't equal type of new model '{}'".format(
                type(old_model_cls).__name__, type(new_model_cls).__name__))

        # check class names
        expected_migrated_model_name = self.models_map[old_model]
        if new_model_cls.__name__ != expected_migrated_model_name:
            inconsistencies.append("models map says '{}' migrates to '{}', but _get_inconsistencies parameters "
                "say '{}' migrates to '{}'".format(old_model, expected_migrated_model_name, old_model,
                    new_model))
        if inconsistencies:
            # given these inconsistencies the checks below would not be informative
            return inconsistencies

        # check types and values of corresponding attributes in old_model and new_model
        # given attr in existing model, need corresponding attr in migrated model
        related_attrs_classes_to_check = ['primary_class', 'related_class']
        scalar_attrs_to_check = ['primary', 'unique', 'unique_case_insensitive']
        for old_attr_name, old_attr in old_model_cls.Meta.attributes.items():
            migrated_class, migrated_attr = self._get_mapped_attribute(old_model, old_attr_name)
            # skip if the attr isn't migrated
            if migrated_attr:
                new_attr = new_model_cls.Meta.attributes[migrated_attr]
                if type(old_attr) != type(new_attr):
                    inconsistencies.append("migrated attribute type mismatch: "
                        "type of {}.{}, {}, doesn't equal type of {}.{}, {}".format(old_model, old_attr_name,
                        type(old_attr).__name__, migrated_class, migrated_attr, type(new_attr).__name__))
                if isinstance(old_attr, obj_model.RelatedAttribute):
                    # ensure that corresponding related attrs have same values of attrs in related_attrs_classes_to_check
                    for related_attrs_class in related_attrs_classes_to_check:
                        old_val = getattr(old_attr, related_attrs_class)
                        old_val_name = getattr(old_val, '__name__') if hasattr(old_val, '__name__') else old_val
                        if old_val_name in self.deleted_models:
                            inconsistencies.append("'{}' is a deleted model, but the migrated attribute '{}.{}' "
                                "refers to it; check model and attribute renaming".format(old_val_name,
                                old_model, old_attr_name))
                        else:
                            new_val = getattr(new_attr, related_attrs_class)
                            new_val_name = getattr(new_val, '__name__') if hasattr(new_val, '__name__') else new_val
                            expected_migrated_model_name = self.models_map[old_val_name]
                            if new_val_name != expected_migrated_model_name:
                                inconsistencies.append(
                                "migrated attribute {}.{}.{} is {} but the model map says {}.{}.{} migrates "
                                    "to {}".format(
                                migrated_class, migrated_attr, related_attrs_class, new_val_name,
                                old_model, old_attr_name, related_attrs_class, expected_migrated_model_name))

                else:
                    for attr_name in scalar_attrs_to_check:
                        old_val = getattr(old_attr, attr_name, None)
                        new_val = getattr(new_attr, attr_name, None)
                        if old_val != new_val:
                            inconsistencies.append("migrated attribute {}.{}.{} is {} but the existing {}.{}.{} is {}".format(
                                migrated_class, migrated_attr, attr_name, new_val,
                                old_model, old_attr_name, attr_name, old_val))

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
                raise ValueError("model '{}' not found in the model map".format(
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
        # todo: remove this hack that ignores Species after Species are stored in their own worksheet
        return [model for model in models.values() if model.Meta.tabular_orientation != TabularOrientation.inline
            and model.__name__ != 'Species']

    def read_existing_model(self, existing_file):
        """ Read models from existing file

        Args:
            existing_file (:obj:`str`): pathname of file to migrate

        Returns:
            :obj:`list` of `obj_model.Model`: the models in `existing_file`
        """
        root, ext = os.path.splitext(existing_file)
        reader = obj_model.io.get_reader(ext)()
        # ignore_sheet_order because models obtained by inspect.getmembers() are returned in name order
        old_models = reader.run(existing_file, models=self._get_models_with_worksheets(self.old_model_defs),
            ignore_attribute_order=True, ignore_sheet_order=True)
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
            :obj:`ValueError`: if migrate_in_place is False and writing the migrated file would
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
                raise ValueError("migrated file '{}' already exists".format(migrated_file))

        # write migrated models to disk
        writer = obj_model.io.get_writer(ext)()
        writer.run(migrated_file, migrated_models, models=model_order)
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
            :obj:`ValueError`: if migrate_in_place is False and writing the migrated file would
                overwrite an existing file
        """
        existing_models = self.read_existing_model(existing_file)
        migrated_models = self.migrate(existing_models)
        # get sequence of migrated models in workbook of existing file
        existing_model_order = self._get_existing_model_order(existing_file)
        migrated_model_order = self._migrate_model_order(existing_model_order)
        migrated_file = self.write_migrated_file(migrated_models, migrated_model_order, existing_file,
            migrated_file=migrated_file, migrate_suffix=migrate_suffix, migrate_in_place=migrate_in_place)
        return migrated_file

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

    def _deep_migrate(self, old_models):
        """ Migrate all model instances from old to new model definitions

        Supports:
            * delete attributes from old schema
            * add attributes in new schema
            * add model definitions in new schema
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
            new_model = self._migrate_model(old_model, old_schema[existing_class_name], new_schema[migrated_class_name])
            all_models.append((old_model, new_model))
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
                        raise ValueError('Invalid related attribute value')  # pragma: no cover

                    setattr(new_model, migrated_attr, migrated_val)

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
            if hasattr(self, attr):
                rv.append("{}: {}".format(attr, getattr(self, attr)))
        for attr in collections_attrs:
            if hasattr(self, attr):
                rv.append("{}:\n{}".format(attr, pformat(getattr(self, attr))))
        return '\n'.join(rv)


class MigrationDesc(object):
    """ Description of a sequence of migrations from an existing file
    """

    _required_attrs = ['name', 'existing_file', 'model_defs_files']
    _renaming_lists = ['renamed_models', 'renamed_attributes']
    _allowed_attrs = _required_attrs + _renaming_lists + ['migrated_file', 'migrate_suffix', 'migrate_in_place']

    def __init__(self, name, existing_file=None, model_defs_files=None, renamed_models=None,
        renamed_attributes=None, migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        self.name = name
        self.existing_file = existing_file
        self.model_defs_files = model_defs_files
        self.renamed_models = renamed_models
        self.renamed_attributes = renamed_attributes
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
        if not errors:
            self.standardize()
        return errors

    def standardize(self):
        """ Standardize
        """
        # convert [model, attr] pairs in renamed_attributes into tuples; needed for hashing
        if self.renamed_attributes:
            new_renamed_attributes = []
            for renamed_attrs_in_a_migration in self.renamed_attributes:
                if renamed_attrs_in_a_migration is None:
                    new_renamed_attributes.append(None)
                    continue
                a_migration_renaming = []
                for existing, migrated in renamed_attrs_in_a_migration:
                    a_migration_renaming.append((tuple(existing), tuple(migrated)))
                new_renamed_attributes.append(a_migration_renaming)
            self.renamed_attributes = new_renamed_attributes

        # if a renaming_list isn't provided, replace it with a list of None indicating no renaming
        empty_per_migration_list = [None]*(len(self.model_defs_files) - 1)
        for renaming_list in self._renaming_lists:
            if getattr(self, renaming_list) is None:
                setattr(self, renaming_list, empty_per_migration_list)

    def get_kwargs(self):
        # get kwargs for optional args
        optional_args = ['existing_file', 'model_defs_files', 'renamed_models', 'renamed_attributes',
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
            :obj:`str`: name of migrated file

        Raises:
            :obj:`ValueError`: if `model_defs_files`, `renamed_models`, and `renamed_attributes`
                are not consistent with each other;
        """
        validate_errors = migration_desc.validate()
        if validate_errors:
            raise ValueError('\n'.join(validate_errors))

        md = migration_desc
        num_migrations = len(md.model_defs_files) - 1
        for i in range(len(md.model_defs_files)):
            # create Migrator for each pair of schemas
            migrator = Migrator(md.model_defs_files[i], md.model_defs_files[i+1], md.renamed_models[i],
                md.renamed_attributes[i])
            migrator.initialize().prepare()
            # migrate in memory until the last migration
            if i == 0:
                models = migrator.read_existing_model(md.existing_file)
                existing_model_order = migrator._get_existing_model_order(md.existing_file)
                model_order = existing_model_order
            models = migrator.migrate(models)
            model_order = migrator._migrate_model_order(model_order)
            if i == num_migrations - 1:
                # done migrating, write to file
                return migrator.write_migrated_file(models, model_order, md.existing_file,
                    migrated_file=md.migrated_file, migrate_suffix=md.migrate_suffix,
                    migrate_in_place=md.migrate_in_place)

    @staticmethod
    def get_migrations_config(migrations_config_file):
        """ Read and initially validate migrations configuration file

        Args:
            migrations_config_file (:obj:`str`): pathname of migrations configuration in YAML file

        Returns:
            :obj:`list` of :obj:`MigrationDesc`: migration descriptions

        Raises:
            :obj:`ValueError`: if `migrations_config_file` cannot be read, or the migration descriptions in
                `migrations_config_file` are not valid
        """
        try:
            fd = open(migrations_config_file, 'r')
        except FileNotFoundError as e:
            raise ValueError("could not read migration config file: '{}'".format(migrations_config_file))
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
            raise ValueError('\n'.join(migration_errors))
        return migration_descs

    @staticmethod
    def migrate_from_desc(migration_desc):
        """ Perform a migration described in a `MigrationDesc`

        Args:
            migration_desc (:obj:`MigrationDesc`): a migration description

        Returns:
            :obj:`str`: migrated filename
        """
        return MigrationController.migrate_over_schema_sequence(migration_desc)

    @staticmethod
    def migrate_from_config(migrations_config_file):
        """ Perform the migrations specified in a config file

        Args:
            migrations_config_file (:obj:`str`): migrations specified in a YAML file

        Returns:
            :obj:`list` of :obj:`str`: migrated filenames
        """
        # todo: document exceptions
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
        migrator.initialize().prepare()
        return migrator.run(args.files)

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
