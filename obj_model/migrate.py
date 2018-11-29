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


# todo: confirm this works for all model file formats: csv, tsv, json, etc.
# todo: error if adding or deleting models or attrs create inconsistencies, as when deleting primary key attr referenced by a foreign key
# todo: support sequence of migrations
#       __init__ (or somewhere else): input list of sequence of schemas
#       _get_all_model_defs: load the sequence of schemas
#       prepare: prepare for a seq of migrations
#       migrate: operate on the sequence of migrations; only write final file to disk
# todo: support renaming of models
#       __init__ (or somewhere else): input model renaming mapping
#       prepare: use mapping when comparing models and checking consistency
#       _get_model_order: use mapping to track model orders
#       deep_migrate & connect_models: use mapping
# todo: support renaming of attributes
#       __init__ (or somewhere else): input attribute renaming mapping, which must be consistent w model renaming mapping
#       _get_inconsistencies, _new_attributes, _deleted_attributes, deep_migrate & connect_models: use mapping
# todo: support arbitrary transformations
# todo: support data driven migration of many files in a repo
#       config file provides: locations of schema files, renaming steps, locations of data files, [dir of migrated files]
#       drive migration from the config file
# todo: support high-level, WC wc_lang specific migration of a repo
#       use case:
#           1 change wc_lang/core.py
#           2 in some repo migrate all model files over multiple wc_lang versions to the new version
#           3 this migration may require arbitrary transformations
#       implementation:
#           each WC repo that has model files maintains a migrate.yml config file with: list of model files to migrate; migration options
#           wc_lang contains migration_transformations.py, which provides all arbitrary transformations
#           "migrate_repo repo" uses repo's migrate.yml and migration_transformations.py to migrate all model files in repo
# todo: support migration in place
# todo: use Model.revision to label git commit of wc_lang and automatically migrate models to current schema
# and to report inconsistency between a schema and model file
# todo: add Meta indicator to models (like Species previously) that are not inline and not stored in their own worksheet
class Migrator(object):
    """ Support schema migration

    Attributes:
        old_model_defs_path (:obj:`str`): pathname of Python file containing old model definitions
        new_model_defs_path (:obj:`str`): pathname of Python file containing new model definitions
        modules (:obj:`dict`): modules being used for migration, indexed by full pathname
        old_model_defs (:obj:`dict`): `obj_model.Model` definitions of the old models, keyed by name
        new_model_defs (:obj:`dict`): `obj_model.Model` definitions of the new models, keyed by name
        deleted_models (:obj:`set`): model types defined in the old models but not the new models
        deleted_attributes (:obj:`str`): deleted attribute names, in (model name, attribute name) pairs
        renamed_models (:obj:`list` of :obj:`tuple`): model types renamed from the existing to the migrated schema
        renamed_models_map (:obj:`dict`): map of model types renamed from the existing to the migrated schema
        renamed_attributes (:obj:`list` of :obj:`tuple`): attribute names renamed from the existing to the migrated schema;
            provided as ((existing model, existing attribute), (migrated model, migrated attribute))
        renamed_attributes_map (:obj:`dict`): map of attribute names renamed from the existing to the migrated schema
        _migrated_copy_attr_name (:obj:`str`): attribute name used to point old models to corresponding
            new models; not used in any old model definitions
        files (:obj:`list`): names of model files to migrate
    """

    # default suffix for a migrated model file
    MIGRATE_SUFFIX = '_migrate'

    # modules being used for migration, indexed by full pathname
    # Migrator does not need or support packages
    modules = {}

    # prefix of attribute name used to connect old and new models during migration
    MIGRATED_COPY_ATTR_PREFIX = '__migrated_copy'

    def __init__(self, old_model_defs_file, new_model_defs_file, files, renamed_models=None,
        renamed_attributes=None):
        """ Initialize a Migrator

        Args:
            old_model_defs_file (:obj:`str`): path of a file containing old Model definitions
            new_model_defs_file (:obj:`str`): path of a file containing new Model definitions
            files (:obj:`list`): file(s) to migrate from old to new Model definitions

        Raises:
            :obj:`ValueError`: if one of the defs files is not a python file
        """
        self.old_model_defs_path = self._normalize_filename(old_model_defs_file)
        self.new_model_defs_path = self._normalize_filename(new_model_defs_file)
        self._valid_python_path(self.old_model_defs_path)
        self._valid_python_path(self.new_model_defs_path)
        self.renamed_models = [] if renamed_models is None else renamed_models
        self.renamed_attributes = [] if renamed_attributes is None else renamed_attributes
        self.files = files

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
        try:
            return self.modules[model_defs_file]
        except KeyError:
            pass

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

    @staticmethod
    def _deleted_attributes(old_model, new_model):
        """ Returns attributes which are in old_model but are not in new_model

        Args:
            old_model (:obj:`obj_model.core.Model`): an original model
            new_model (:obj:`obj_model.core.Model`): a new model

        Returns:
            :obj:`list`: names of deleted attributes
        """
        deleted_attributes = []
        for attr in old_model.Meta.attributes:
            if attr not in new_model.Meta.attributes:
                deleted_attributes.append(attr)
        return deleted_attributes

    @staticmethod
    # todo: put in or get from utils
    def _get_duplicates(iter):
        """ Obtain duplicates in iterable `iter`; assumes items in `iter` are hashable

        Args:
            module (:obj:`iter`): an iterable

        Returns:
            :obj:`set`: duplicated items in `l`
        """
        seen = set()
        dupes = set()

        for item in iter:
            if item not in seen:
                seen.add(item)
            else:
                dupes.add(item)
        return dupes

    def _verify_renamings(self):
        """ Verify that renamed models and attributes refer to the existing schema and migrated schema

        Also verify no renaming inconsistencies and create maps from existing to migrated renamed
        models and attributes.

        Raises:
            :obj:`ValueError`: if models or attributes do not exist in the specified schema
        """
        errors = []

        # check renamed models
        for existing_model, migrated_model in self.renamed_models:
            if existing_model not in self.old_model_defs:
                errors.append("'{}' in renamed models not an existing model".format(existing_model))
            if migrated_model not in self.new_model_defs:
                errors.append("'{}' in renamed models not a migrated model".format(migrated_model))
        duped_existing_models = self._get_duplicates([existing_model for existing_model, _ in self.renamed_models])
        if duped_existing_models:
                errors.append("duplicated existing models in renamed models: '{}'".format(duped_existing_models))
        duped_migrated_models = self._get_duplicates([migrated_model for _, migrated_model in self.renamed_models])
        if duped_migrated_models:
                errors.append("duplicated migrated models in renamed models: '{}'".format(duped_migrated_modelss))

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
            # i.e., if an attribute is renamed A.x -> B.y then the model A must be renamed A -> B
            if existing_model not in self.renamed_models_map or \
                migrated_model != self.renamed_models_map[existing_model]:
                errors.append("model renaming '{} -> {}' in renamed attributes not renamed models".format(
                    existing_model, migrated_model))
        duped_existing_attributes = self._get_duplicates([existing_attr for existing_attr, _ in self.renamed_attributes])
        if duped_existing_attributes:
                errors.append("duplicated existing attributes in renamed attributes: '{}'".format(duped_existing_attributes))
        duped_migrated_attributes = self._get_duplicates([migrated_attr for _, migrated_attr in self.renamed_attributes])
        if duped_migrated_attributes:
                errors.append("duplicated migrated attributes in renamed attributes: '{}'".format(duped_migrated_attributes))

        if errors:
            raise ValueError('\n'.join(errors))

        self.renamed_models_map = dict(self.renamed_models)
        self.renamed_attributes_map = dict(self.renamed_attributes)

    def _get_paired_models(self):
        """ Obtain names of mapped pairs of existing and migrated models

        Assumes that models with the same name are paired unless they're specified in `self.renamed_models`

        Returns:
            :obj:`list` of `tuple`: (existing_model, migrated_model) pairs for all models that are migrated
        """
        paired_models = []

        for model in self.old_model_defs:
            if model in self.renamed_models_map:
                paired_models.append((model, self.renamed_models_map[model]))
            if model in self.new_model_defs:
                paired_models.append((model, model))
        return paired_models

    def prepare(self):
        """ Prepare for migration

        Raises:
            :obj:`ValueError`: if renamings are not valid, or
                inconsistencies exist between corresponding old and migrated classes
        """
        self._get_all_model_defs()

        # verify that renaming specification refers to existing and migrated models & attributes
        self._verify_renamings()

        # compare models
        # fix: use model renaming
        self.deleted_models = set(self.old_model_defs).difference(self.new_model_defs)

        # list of (model name, attribute name) pairs
        self.deleted_attributes = []
        # compare models that are both old and new
        # fix or discard
        for existing_model, migrated_model in self._get_paired_models():
            for attr in self._deleted_attributes(self.old_model_defs[existing_model], self.new_model_defs[migrated_model]):
                self.deleted_attributes.append((migrated_model, attr))

        # check that models in old and new are consistent
        inconsistencies = []
        for existing_model, migrated_model in self._get_paired_models():
            inconsistencies.extend(self._get_inconsistencies(self.old_model_defs[existing_model],
                self.new_model_defs[migrated_model]))
        if inconsistencies:
            raise ValueError('\n'.join(inconsistencies))

        # get attribute name not used in old model definitions so that old models can point to new models
        self._migrated_copy_attr_name = self._get_migrated_copy_attr_name()

    @staticmethod
    def _get_inconsistencies(old_model_cls, new_model_cls):
        """ Returns inconsistencies between old_model_cls and new_model_cls

        Args:
            old_model_cls (:obj:`obj_model.core.ModelMeta`): an old model class
            new_model_cls (:obj:`obj_model.core.ModelMeta`): the corresponding new model class

        Returns:
            :obj:`list`: inconsistencies between old_model_cls and new_model_cls; an empty list if
                no inconsistencies exist
        """
        inconsistencies = []

        # check types
        if type(old_model_cls) != type(new_model_cls): # pragma: no cover: types other than obj_model.core.ModelMeta fail below
            inconsistencies.append("types differ: old model '{}' != new model '{}'".format(
                type(old_model_cls).__name__, type(new_model_cls).__name__))

        # check class names
        if old_model_cls.__name__ != new_model_cls.__name__:
            inconsistencies.append("names differ: old model '{}' != new model '{}'".format(
                old_model_cls.__name__, new_model_cls.__name__))
        cls_name = old_model_cls.__name__

        # check types and values of attributes with the same name in old_model_cls and new_model_cls
        # fix: use attr renaming
        related_attrs_to_check = ['name', 'related_name', 'verbose_related_name']
        related_attrs_names_to_check = ['primary_class', 'related_class']
        scalar_attrs_to_check = ['name', 'primary', 'unique', 'unique_case_insensitive']
        for old_attr_name, old_attr in old_model_cls.Meta.attributes.items():
            if old_attr_name in new_model_cls.Meta.attributes:
                new_attr = new_model_cls.Meta.attributes[old_attr_name]
                if type(old_attr) != type(new_attr):
                    inconsistencies.append("{}: types differ for '{}': old model '{}' != new model '{}'".format(
                        cls_name, old_attr_name, type(old_attr).__name__, type(new_attr).__name__))
                if isinstance(old_attr, obj_model.RelatedAttribute):
                    for related_attrs_name in related_attrs_names_to_check:
                        old_val = getattr(old_attr, related_attrs_name, None)
                        old_val_name = getattr(old_val, '__name__', None)
                        new_val = getattr(new_attr, related_attrs_name, None)
                        new_val_name = getattr(new_val, '__name__', None)
                        if old_val_name != new_val_name:
                            inconsistencies.append("{}: names differ for '{}.{}': old model '{}' != new model '{}'".format(
                                cls_name, old_attr_name, related_attrs_name, old_val_name, new_val_name))

                    attrs_to_check = related_attrs_to_check
                else:
                    attrs_to_check = scalar_attrs_to_check

                for attr_name in attrs_to_check:
                    old_val = getattr(old_attr, attr_name, None)
                    new_val = getattr(new_attr, attr_name, None)
                    if old_val != new_val:
                        inconsistencies.append("{}: '{}' differs for '{}': old model '{}' != new model '{}'".format(
                            cls_name, attr_name, old_attr_name, old_val, new_val))
        return inconsistencies

    @staticmethod
    def _get_model_order(source_file, old_models, new_models):
        """ Returns sequence of models in source_file

        Args:
            source_file (:obj:`str`): pathname of file being migrated
            old_models (:obj:`dict` of `obj_model.core.ModelMeta`): the original model classes
            new_models (:obj:`dict` of `obj_model.core.ModelMeta`): the new model classes

        Returns:
            :obj:`list` of `obj_model.core.ModelMeta`: migrated models in the same order as the worksheets
                for the corresponding old models, concatenated with new models sorted by name
        """
        # todo: clean up naming: old models, existing, migrated models, new models, source models, dest models
        # use sheet_names in old file to determine order of model types in old source file, and use them in migrated file
        _, ext = os.path.splitext(source_file)
        utils_reader = wc_utils.workbook.io.get_reader(ext)(source_file)
        utils_reader.initialize_workbook()
        sheet_names = utils_reader.get_sheet_names()

        old_models_migrating = []
        new_models_migrated = []
        # fix: use model renaming
        for migrated_model_name in set(old_models).intersection(new_models):
            old_models_migrating.append(old_models[migrated_model_name])
            new_models_migrated.append(new_models[migrated_model_name])

        # detect sheets that cannot be unambiguously mapped
        ambiguous_sheet_names = WorkbookReader.get_ambiguous_sheet_names(sheet_names, old_models_migrating)
        if ambiguous_sheet_names:
            msg = 'The following sheets cannot be unambiguously mapped to models:'
            for sheet_name, models in ambiguous_sheet_names.items():
                msg += '\n  {}: {}'.format(sheet_name, ', '.join(model.__name__ for model in models))
            warn(msg, IoWarning)

        # use the source_file sheet names to establish order of old models that get migrated
        tmp = []
        for old_model_migrating, new_model_migrated in zip(old_models_migrating, new_models_migrated):
            try:
                sheet_name = WorkbookReader.get_model_sheet_name(sheet_names, old_model_migrating)
                if sheet_name is not None:
                    tmp.append((sheet_names.index(sheet_name), new_model_migrated))
            except ValueError:
                pass
        tmp.sort(key=lambda position_n_model: position_n_model[0])
        migrated_model_order = [position_n_model[1] for position_n_model in tmp]

        # append newly created models
        newly_created_model_names = []
        for newly_created_model_name in set(new_models).difference(old_models):
            newly_created_model_names.append(newly_created_model_name)
        newly_created_model_names.sort()
        newly_created_models = [new_models[name] for name in newly_created_model_names]

        migrated_model_order.extend(newly_created_models)
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

    def migrate(self, source_file, migrated_file=None, migrate_suffix=None):
        """ Migrate data in `source_file`

        Args:
            source_file (:obj:`str`): pathname of file to migrate
            migrated_file (:obj:`str`, optional): pathname of migrated file; if not provided,
                save migrated file with new suffix in same directory as source file
            migrate_suffix (:obj:`str`, optional): suffix of automatically created migrated filename

        Returns:
            :obj:`str`: name of migrated file

        Raises:
            :obj:`ValueError`: if writing the migrated file would overwrite an existing file
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
        if migrate_suffix is None:
            migrate_suffix = Migrator.MIGRATE_SUFFIX
        if migrated_file is None:
            migrated_file = os.path.join(os.path.dirname(source_file),
                os.path.basename(root) + migrate_suffix + ext)
        if os.path.exists(migrated_file):
            raise ValueError("migrated file '{}' already exists".format(migrated_file))

        # get sequence of migrated models in workbook
        models = self._get_model_order(source_file, self.old_model_defs, self.new_model_defs)

        # write migrated models to disk
        writer = obj_model.io.get_writer(ext)()
        writer.run(migrated_file, new_models, models=models)
        return migrated_file

    def migrate_model(self, old_model, old_model_def, new_model_def):
        """ Migrate a Model instance's non-related attributes

        Args:
            old_model (:obj:`obj_model.Model`): the old model
            old_model_def (:obj:`obj_model.core.ModelMeta`): type of the old model
            new_model_def (:obj:`obj_model.core.ModelMeta`): type of the new model

        Returns:
            :obj:`obj_model.Model`: a `new_model_def` instance migrated from `old_model`
        """
        model_name = old_model_def.__name__
        new_model = new_model_def()

        # fix: use attr renaming
        # copy non-Related attributes from old_model to new_model
        for attr in old_model_def.Meta.attributes.values():
            val = getattr(old_model, attr.name)

            # skip attributes that are not in new_model_def
            if (model_name, attr) in self.deleted_attributes:
                continue

            if not isinstance(attr, obj_model.RelatedAttribute):
                if val is None:
                    copy_val = val
                elif isinstance(val, (string_types, bool, integer_types, float, Enum, )):
                    copy_val = val
                else:
                    copy_val = copy.deepcopy(val)

                setattr(new_model, attr.name, copy_val)

        # save reference to the new model in old_model, which is used by connect_models()
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
        # fix: use model renaming
        for old_model in old_models:
            cls_name = old_model.__class__.__name__

            # do not migrate models whose classes are not in the new schema
            if cls_name in self.deleted_models:
                continue

            new_model = self.migrate_model(old_model, old_schema[cls_name], new_schema[cls_name])
            all_models.append((old_model, new_model))
        return all_models

    def connect_models(self, all_models):
        """ Connect migrated Model instances

        Copy `obj_model.RelatedAttribute` connections among old models to new models

        Args:
            all_models (:obj:`list`): pairs of corresponding old and new model instances
        """
        for old_model, new_model in all_models:
            new_model_cls = new_model.__class__
            # fix: use attr renaming
            for attr in new_model_cls.Meta.attributes.values():

                if isinstance(attr, obj_model.RelatedAttribute):
                    val = getattr(old_model, attr.name)
                    if val is None:
                        copy_val = val
                    elif isinstance(val, obj_model.core.Model):
                        copy_val = getattr(val, self._migrated_copy_attr_name)
                    elif isinstance(val, (set, list, tuple)):
                        copy_val = []
                        for model in val:
                            copy_val.append(getattr(model, self._migrated_copy_attr_name))
                    else:
                        # unreachable due to other error checking
                        raise ValueError('Invalid related attribute value')  # pragma: no cover

                    setattr(new_model, attr.name, copy_val)

    def run(self):
        migrated_files = []
        for file in self.files:
            # todo: provide CL means to supply migrated_file and migrate_suffix
            migrated_files.append(self.migrate(self._normalize_filename(file)))
        return migrated_files


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
        migrator.prepare()
        return migrator.run()

if __name__ == '__main__':  # pragma: no cover     # reachable only from command line
    try:
        args = RunMigration.parse_args(sys.argv[1:])
        RunMigration.main(args)
    except KeyboardInterrupt:
        pass
