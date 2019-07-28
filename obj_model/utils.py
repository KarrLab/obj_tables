""" Utilities

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from __future__ import unicode_literals
from itertools import chain
from pathlib import Path
from random import shuffle
import collections
from obj_model.core import (Model, Attribute, StringAttribute, RelatedAttribute, InvalidObjectSet,
    InvalidObject, Validator, TabularOrientation)
from wc_utils.util import git
import obj_model


def get_related_models(root_model, include_root_model=False):
    """ Get the models that have relationships to a model

    Args:
        root_model (:obj:`type`): subclass of :obj:`Model`
        include_root_model (:obj:`bool`, optional): include the root model in the returned list of models

    Returns:
        :obj:`list` of :obj:`type`: list of models that have relationships with :obj:`root_model`
    """
    related_models = [root_model]
    to_check = [root_model]
    while to_check:
        cur_model = to_check.pop()

        for attr in cur_model.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute) and attr.related_class not in related_models:
                related_models.append(attr.related_class)
                to_check.append(attr.related_class)

        for attr in cur_model.Meta.related_attributes.values():
            if attr.primary_class not in related_models:
                related_models.append(attr.primary_class)
                to_check.append(attr.primary_class)

    if not include_root_model:
        related_models.pop(0)

    return related_models


def get_attribute_by_name(cls, group_name, attr_name, verbose_name=False, case_insensitive=False):
    """ Return the attribute of `Model` class `cls` with name `name`

    Args:
        cls (:obj:`class`): Model class
        group_name (:obj:`str`): name of attribute group
        attr_name (:obj:`str`): attribute name
        verbose_name (:obj:`str`): if :obj:`True`, search for attributes by verbose name; otherwise search for attributes by name
        case_insensitive (:obj:`bool`, optional): if True, ignore case

    Returns:
        :obj:`Attribute`: attribute with name equal to the value of `group_name` or `None` if there is no matching attribute
        :obj:`Attribute`: attribute with name equal to the value of `attr_name` or `None` if there is no matching attribute
    """

    if not attr_name:
        return (None, None)

    attr_order = list(cls.Meta.attribute_order)
    attr_order.extend(list(set(cls.Meta.attributes.keys()).difference(set(attr_order))))

    for attr_name_to_search in attr_order:
        attr = cls.Meta.attributes[attr_name_to_search]
        if group_name is None:
            if (not case_insensitive and ((not verbose_name and attr.name == attr_name)
                                          or (verbose_name and attr.verbose_name == attr_name))) or \
                (case_insensitive and ((not verbose_name and attr.name.lower() == attr_name.lower())
                                       or (verbose_name and attr.verbose_name.lower() == attr_name.lower()))):
                return (None, attr)
        else:
            if isinstance(attr, RelatedAttribute) and attr.related_class.Meta.tabular_orientation == TabularOrientation.multiple_cells:
                if attr.name.lower() == group_name.lower() or attr.verbose_name.lower() == group_name.lower():
                    sub_attr = get_attribute_by_name(attr.related_class, None, attr_name, verbose_name=verbose_name,
                                                     case_insensitive=case_insensitive)
                    return (attr, sub_attr[1])

    return (None, None)


def group_objects_by_model(objects):
    """ Group objects by their models

    Args:
        objects (:obj:`list` of :obj:`Model`): list of model objects

    Returns:
        :obj:`dict`: dictionary with object grouped by their class
    """
    grouped_objects = {}
    for obj in objects:
        if not obj.__class__ in grouped_objects:
            grouped_objects[obj.__class__] = []
        if obj not in grouped_objects[obj.__class__]:
            grouped_objects[obj.__class__].append(obj)
    return grouped_objects


def get_related_errors(object):
    """ Get all errors associated with an object and its related objects

    Args:
        object (:obj:`Model`): object

    Returns:
        :obj:`InvalidObjectSet`: set of errors
    """
    objects = object.get_related()
    if object not in objects:
        objects.append(object)
    return Validator().run(objects)


def get_component_by_id(models, id, identifier='id'):
    ''' Retrieve a model instance by its identifier

    Args:
        model (:obj:list of `Model`): an iterable of `Model` objects
        id (:obj:`str`): the identifier being sought
        identifier (:obj:`str`, optional): the name of the identifier attribute

    Returns:
        :obj:`Model`: the retrieved Model instance if found, or None

    Raises:
        :obj:`AttributeError`: if `model` does not have the attribute specified by `identifier`
    '''
    # TODO: this is O(n); achieve O(1) by using Manager() dictionaries id -> component for each model
    for model in models:
        try:
            if getattr(model, identifier) == id:
                return model
        except AttributeError as e:
            raise AttributeError("{} does not have the attribute '{}'".format(model.__class__.__name__,
                                                                              identifier))
    return None


def randomize_object_graph(obj):
    """ Randomize the order of the edges (RelatedManagers) in the object's object graph.

    Args:
        obj (:obj:`Model`): instance of :obj:`Model`
    """
    randomized_objs = []
    objs_to_randomize = [obj]

    while objs_to_randomize:
        obj = objs_to_randomize.pop()
        if obj not in randomized_objs:
            randomized_objs.append(obj)

            for attr_name, attr in chain(obj.Meta.attributes.items(), obj.Meta.related_attributes.items()):
                if isinstance(attr, RelatedAttribute):
                    val = getattr(obj, attr_name)
                    if isinstance(val, list) and len(val) > 1:
                        # randomize children
                        objs_to_randomize.extend(val)

                        # shuffle related manager
                        shuffle(val)


def source_report(obj, attr_name):
    """ Get the source file, worksheet, column, and row location of attribute `attr_name` of
    model object `obj` as a colon-separated string.

    Args:
        obj (:obj:`Model`): model object
        attr_name (:obj:`str`): attribute name

    Returns:
        :obj:`str`: a string representation of the source file, worksheet, column, and row
            location of `attr_name` of `obj`
    """
    ext, filename, worksheet, row, column = obj.get_source(attr_name)
    if 'xlsx' in ext:
        return "{}:{}:{}{}".format(filename, worksheet, column, row)
    else:
        return "{}:{}:{},{}".format(filename, worksheet, row, column)


def set_git_repo_metadata_from_path(model, repo_type, path='.', url_attr='url', branch_attr='branch',
                                    commit_hash_attr='revision'):
    """ Use Git to set the Git repository URL, branch, and commit hash metadata attributes of a model

    Args:
        model (:obj:`Model`): model whose Git attributes will be set
        repo_type (:obj:`git.RepoMetadataCollectionType`): repo type being set
        path (:obj:`str`, optional): path to file or directory in a clone of a Git repository; default='.'
        url_attr (:obj:`str`, optional): attribute in `model` for the Git URL; default='url'
        branch_attr (:obj:`str`, optional): attribute in `model` for the Git branch; default='branch'
        commit_hash_attr (:obj:`str`, optional): attribute in `model` for the Git commit hash;
            default='revision'

    Returns:
        :obj:`list` of :obj:`str`: list of reasons, if any, that the repo might not be
            suitable for collecting metadata
    """
    md, unsuitable_changes = git.get_repo_metadata(path=path, repo_type=repo_type, data_file=path)
    setattr(model, url_attr, md.url)
    setattr(model, branch_attr, md.branch)
    setattr(model, commit_hash_attr, md.revision)
    return unsuitable_changes


# Git repository metadata from an `obj_model` data file
DataFileMetadata = collections.namedtuple('DataFileMetadata', 'data_repo_metadata, schema_repo_metadata')
DataFileMetadata.__doc__ += ': Git repository metadata from an obj_model data file'
DataFileMetadata.data_repo_metadata.__doc__ = "Git metadata about the repository containing the file"
DataFileMetadata.schema_repo_metadata.__doc__ = \
    "Git metadata about the repository containing the obj_model schema used by the file"


def read_metadata_from_file(pathname):
    """ Read Git repository metadata from an `obj_model` data file

    Args:
        pathname (:obj:`str`): path to the data file

    Returns:
        :obj:`DataFileMetadata`: data and schema repo metadata from the file at `pathname`; missing
        metadata is returned as :obj:`None`

    Raises:
        :obj:`ValueError`: if `pathname`'s extension is not supported,
            or unexpected metadata instances are found
    """
    reader = obj_model.io.Reader.get_reader(pathname)

    metadata_instances = reader().run(pathname, [DataRepoMetadata, SchemaRepoMetadata],
        ignore_extra_sheets=True, ignore_missing_sheets=True, group_objects_by_model=True,
        ignore_attribute_order=True)
    metadata_class_to_attr = {
        DataRepoMetadata: 'data_repo_metadata',
        SchemaRepoMetadata: 'schema_repo_metadata'
    }
    data_file_metadata_dict = {
        'data_repo_metadata': None,
         'schema_repo_metadata': None
    }
    for model_class, instances in metadata_instances.items():
        if len(instances) == 1:
            data_file_metadata_dict[metadata_class_to_attr[model_class]] = instances[0]
        elif 1 < len(instances):
            raise ValueError("Multiple instances of {} found in '{}'".format(model_class.__name__,
                pathname))
    return DataFileMetadata(**data_file_metadata_dict)


# todo: make this more convenient by eliminating models. either a) change schema_package to the path
# to the schema and use the modules in it, or b) use wc_utils.workbook.io to copy all data in
# the existing file and using WriterBase.make_metadata_objects() to obtain the metadata
# todo: make a CLI command for add_metadata_to_file -- it will need to use IO classes like migrate.py
def add_metadata_to_file(pathname, models, schema_package=None):
    """ Add Git repository metadata to an existing `obj_model` data file

    Overwrites the existing file

    Args:
        pathname (:obj:`str`): path to an `obj_model` data file in a Git repo
        models (:obj:`list` of :obj:`types.TypeType`, optional): list of types of objects to read
        schema_package (:obj:`str`, optional): the package which defines the `obj_model` schema
            used by the file; if not :obj:`None`, try to write metadata information about the
            the schema's Git repository: the repo must be current with origin

    Returns:
        :obj:`str`: pathname of new data file

    Raises:
        :obj:`ValueError`: if `overwrite` is not set the new file would overwrite an existing file
    """
    # read file
    path = Path(pathname).resolve()
    objects = obj_model.io.Reader().run(str(path), models=models)
    # write file with metadata
    obj_model.io.Writer().run(str(path), objects, models=models, data_repo_metadata=True,
        schema_package=schema_package)
    return path


class RepoMetadata(Model):
    """ Generic Model to store Git version information about a repo """
    url = StringAttribute()
    branch = StringAttribute()
    revision = StringAttribute()

    class Meta(Model.Meta):
        tabular_orientation = TabularOrientation.column
        attribute_order = ('url', 'branch', 'revision')


class DataRepoMetadata(RepoMetadata):
    """ Model to store Git version information about a data file's repo """
    pass


class SchemaRepoMetadata(RepoMetadata):
    """ Model to store Git version info for the repo that defines the obj_model schema used by a data file """
    pass
