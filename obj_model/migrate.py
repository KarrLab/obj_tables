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
from six import integer_types, string_types
from enum import Enum
from warnings import warn

import obj_model
from obj_model import TabularOrientation
from obj_model.io import WorkbookReader, IoWarning
import wc_utils
from wc_utils.util.list import det_find_dupes


# local
# todo next: rename these to local methods: migrate_model, deep_migrate, connect_models,
# todo next: changes for migrate_over_schema_sequence
# todo next: confirm this works for all model file formats: csv, tsv, json, etc.
# todo next: support sequence of migrations: in a new class; also, migrate without writing file
# todo next: clean up naming: old models, existing, migrated models, new models, source models, dest models
# todo next: support data driven migration of many files [in a repo]
#       config file provides: locations of schema file pair, renaming steps between them, locations of data & migrated files
#       drive migration from the config file
# todo next: support arbitrary transformations by an optional function on each migrated instance

# global
# todo next: make work with full wc_lang core.py

# Model change
# todo next: separately specified default value for attribute
# todo next: add Meta indicator to models (like Species previously) that are not inline and not stored in their own worksheet
#   and remove Species hack

# todo next: move remaining todos to GitHub issues
# todo: confirm this works for json, etc.
# todo: test sym links in Migrator._normalize_filename
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
        files (:obj:`list`): names of model files to migrate
    """

    # default suffix for a migrated model file
    MIGRATE_SUFFIX = '_migrated'

    # modules being used for migration, indexed by full pathname
    # Migrator does not need or support packages
    modules = {}

    # prefix of attribute name used to connect old and new models during migration
    MIGRATED_COPY_ATTR_PREFIX = '__migrated_copy'

    def __init__(self, old_model_defs_file, new_model_defs_file, files, renamed_models=None,
        renamed_attributes=None):
        """ Construct a Migrator

        Args:
            old_model_defs_file (:obj:`str`): path of a file containing old Model definitions
            new_model_defs_file (:obj:`str`): path of a file containing new Model definitions
            files (:obj:`list`): file(s) to migrate from old to new Model definitions
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
        self.files = files

    def initialize(self):
        """ Initialize a Migrator

        Separate from prepare() so most of Migrator can be tested with models defined in code
        """
        self.old_model_defs_path = self._normalize_filename(self.old_model_defs_file)
        self.new_model_defs_path = self._normalize_filename(self.new_model_defs_file)
        self._valid_python_path(self.old_model_defs_path)
        self._valid_python_path(self.new_model_defs_path)

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
            # return these inconsistencies because checks below would not be informative
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
                        new_val = getattr(new_attr, related_attrs_class)
                        new_val_name = getattr(new_val, '__name__') if hasattr(new_val, '__name__') else new_val
                        expected_migrated_model_name = self.models_map[old_val_name]
                        if new_val_name != expected_migrated_model_name:
                            inconsistencies.append(
                            "migrated attribute {}.{}.{} is {} but the model map says {}.{}.{} migrates to {}".format(
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

    def _get_model_order(self, source_file):
        """ Provide the sequence in which models should appear in the migrated file

        First determine the order of existing model types in worksheets in the source file. However, the
        mapping of some worksheets to models may be ambiguous. Then map the order to the migrated models,
        which is used to sequence worksheets or files in the migrated file(s).

        Args:
            source_file (:obj:`str`): pathname of file being migrated

        Returns:
            :obj:`list` of `obj_model.core.ModelMeta`: migrated models in the same order as worksheets
                for the corresponding old models, followed by migrated models with ambiguous sheet
                names, followed by new models sorted by name
        """
        _, ext = os.path.splitext(source_file)
        utils_reader = wc_utils.workbook.io.get_reader(ext)(source_file)
        utils_reader.initialize_workbook()
        sheet_names = utils_reader.get_sheet_names()

        existing_models_migrating = []
        migrated_models = []
        for existing_model, migrated_model in self.models_map.items():
            existing_models_migrating.append(self.old_model_defs[existing_model])
            migrated_models.append(self.new_model_defs[migrated_model])

        # detect sheets that cannot be unambiguously mapped
        ambiguous_sheet_names = WorkbookReader.get_ambiguous_sheet_names(sheet_names, existing_models_migrating)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            warn(msg, IoWarning)

        # use the source_file sheet names to establish order of existing models that get migrated
        migrated_model_order = [None]*len(sheet_names)
        ambiguous_migrated_models = []
        for existing_model, migrated_model in zip(existing_models_migrating, migrated_models):
            try:
                sheet_name = WorkbookReader.get_model_sheet_name(sheet_names, existing_model)
                if sheet_name is not None:
                    migrated_model_order[sheet_names.index(sheet_name)] = migrated_model
            except ValueError:
                ambiguous_migrated_models.append(migrated_model)
        migrated_model_order = [element for element in migrated_model_order if element is not None]

        # append migrated models with ambiguous sheet
        migrated_model_order.extend(ambiguous_migrated_models)

        # append newly created models
        new_model_names = [new_model_name
            for new_model_name in set(self.new_model_defs).difference(self.models_map.values())]
        new_models = [self.new_model_defs[name] for name in sorted(new_model_names)]
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

    def migrate(self, source_file, migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        """ Migrate data in `source_file`

        Args:
            source_file (:obj:`str`): pathname of file to migrate
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
        # read models from source_file
        root, ext = os.path.splitext(source_file)
        reader = obj_model.io.get_reader(ext)()
        # ignore_sheet_order because models obtained by inspect.getmembers() are returned in name order
        old_models = reader.run(source_file, models=self._get_models_with_worksheets(self.old_model_defs),
            ignore_attribute_order=True, ignore_sheet_order=True)
        models_read = []
        for models in old_models.values():
            models_read.extend(models)

        # migrate model instances to new schema
        all_models = self.deep_migrate(models_read)
        self.connect_models(all_models)
        new_models = [new_model for _, new_model in all_models]

        # determine pathname of migrated file
        if migrate_in_place:
            migrated_file = source_file
        else:
            if migrate_suffix is None:
                migrate_suffix = Migrator.MIGRATE_SUFFIX
            if migrated_file is None:
                migrated_file = os.path.join(os.path.dirname(source_file),
                    os.path.basename(root) + migrate_suffix + ext)
            if os.path.exists(migrated_file):
                raise ValueError("migrated file '{}' already exists".format(migrated_file))

        # get sequence of migrated models in workbook
        models = self._get_model_order(source_file)

        # write migrated models to disk
        writer = obj_model.io.get_writer(ext)()
        writer.run(migrated_file, new_models, models=models)
        return migrated_file

    def migrate_model(self, old_model, old_model_def, new_model_def):
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

        # save a reference to new_model in old_model, which is used by connect_models()
        setattr(old_model, self._migrated_copy_attr_name, new_model)
        return new_model

    def deep_migrate(self, old_models):
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
            new_model = self.migrate_model(old_model, old_schema[existing_class_name], new_schema[migrated_class_name])
            all_models.append((old_model, new_model))
        return all_models

    def connect_models(self, all_models):
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

    def run(self):
        migrated_files = []
        for file in self.files:
            migrated_files.append(self.migrate(self._normalize_filename(file)))
        return migrated_files


class MigrationController(object):
    """ Manage multiple migrations and underspecified migrations

    Manage migrations on several dimensions:
    * Migrate a single model file through a sequence of schemas
    * Perform migrations parameterized by a configuration file
    """

    def __init__(self):
        """ Construct a MigrationController
        """
        pass

    def migrate_over_schema_sequence(self, source_file, model_defs_files,
        renamed_models=None, renamed_attributes=None,
        migrated_file=None, migrate_suffix=None, migrate_in_place=False):
        """ Migrate a model file over a sequence of schemas

        Args:
            x (:obj:`list`): y
            ...

        Returns:
            :obj:`str`: name of migrated file

        Raises:
            :obj:`ValueError`: if `model_defs_files`, `renamed_models`, and `renamed_attributes`
                are not consistent with each other;
        """
        model_defs_files, renamed_models, renamed_attributes = self._check_params('migrate_over_schema_sequence',
            dict(model_defs_files=model_defs_files, renamed_models=renamed_models, renamed_attributes=renamed_attributes))
        num_migrations = len(model_defs_files) - 1
        for i in range(len(model_defs_files)):
            # todo: move files elsewhere
            # create Migrator for each pair of schemas
            migrator = Migrator(model_defs_files[i], model_defs_files[i+1], [], renamed_models[i], renamed_attributes[i])
            migrator.initialize()
            migrator.prepare()
            # todo: return_models option on migrate(), separate out '# migrate model instances to new schema' to 'migrate'
            # add 'read_existing_model', 'write_migrated_file'
            # migrate in memory until the last migration
            if i == 0:
                models = migrator.read_existing_model(source_file)
            models = migrator.migrate(models)
            if i == num_migrations - 1:
                # done migrating, write to file
                migrated_filename = migrator.write_migrated_file(models, migrated_file=migrated_file,
                    migrate_suffix=migrate_suffix, migrate_in_place=migrate_in_place)

    @staticmethod
    def _check_params(param_set, **kwargs):
        if param_set == 'migrate_over_schema_sequence':
            model_defs_files = kwargs['model_defs_files']
            renamed_models = kwargs['renamed_models']
            renamed_attributes = kwargs['renamed_attributes']
            model_defs_files = list(model_defs_files)
            if len(model_defs_files) < 2:
                raise ValueError("model_defs_files must contain at least 2 model definitions, but "
                    "it has only {}".format(len(model_defs_files)))
            if renamed_models is not None:
                renamed_models = list(renamed_models)
                if len(renamed_models) != len(model_defs_files) - 1:
                    raise ValueError("model_defs_files specifies {} migration(s), but renamed_models "
                        "contains {} rename mapping(s)".format(
                            len(model_defs_files) - 1, len(renamed_models)))
            if renamed_attributes is not None:
                renamed_attributes = list(renamed_attributes)
                if len(renamed_attributes) != len(model_defs_files) - 1:
                    raise ValueError("model_defs_files specifies {} migration(s), but renamed_attributes "
                        "contains {} rename mapping(s)".format(
                            len(model_defs_files) - 1, len(renamed_attributes)))
            return (model_defs_files, renamed_models, renamed_attributes)

    def migrate_from_configuration_file(self):
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
        migrator = Migrator(args.existing_model_definitions, args.new_model_definitions, args.files)
        migrator.initialize()
        migrator.prepare()
        return migrator.run()

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
