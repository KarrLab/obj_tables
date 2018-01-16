""" Utilities

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from __future__ import unicode_literals
from itertools import chain
from random import shuffle
from obj_model.core import Model, Attribute, RelatedAttribute, InvalidObjectSet, InvalidObject, Validator


def get_attribute_by_name(cls, name, case_insensitive=False):
    """ Return the attribute of `Model` class `cls` with name `name`

    Args:
        cls (:obj:`class`): Model class
        name (:obj:`str`): attribute name
        case_insensitive (:obj:`bool`, optional): if True, ignore case

    Returns:
        :obj:`Attribute`: attribute with name equal to the value of `name` or `None`
        if there is no matching attribute
    """

    if not name:
        return None
    for attr_name, attr in cls.Meta.attributes.items():
        if not case_insensitive and attr_name == name:
            return attr
        if case_insensitive and attr_name.lower() == name.lower():
            return attr
    return None


def get_attribute_by_verbose_name(cls, verbose_name, case_insensitive=False):
    """ Return the attribute of `Model` class `cls` with verbose name `verbose_name`

    Args:
        cls (:obj:`class`): Model class
        verbose_name (:obj:`str`): verbose attribute name
        case_insensitive (:obj:`bool`, optional): if True, ignore case

    Returns:
        :obj:`Attribute`: attribute with verbose name equal to the value of `verbose_name` or `None`
        if there is no matching attribute
    """

    if not verbose_name:
        return None
    for attr_name, attr in cls.Meta.attributes.items():
        if not case_insensitive and attr.verbose_name == verbose_name:
            return attr
        if case_insensitive and attr.verbose_name.lower() == verbose_name.lower():
            return attr
    return None


def group_objects_by_model(objects):
    """ Group objects by their models

    Args:
        objects (:obj:`list` of `Model`): list of model objects

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
