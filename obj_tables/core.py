""" Toolkit for modeling complex datasets with collections of user-friendly tables

Many classes contain the methods `serialize()` and `deserialize()`, which invert each other.
`serialize()` converts a python object instance into a string representation, whereas
`deserialize()` parses an object's string representation -- as would be stored in a file or spreadsheet
representation of a biochemical model -- into a python object instance.
`deserialize()` returns an error when the string representation cannot be parsed into the
python object. Deserialization methods for related attributes (subclasses of `RelatedAttribute`)
do not get called until all other attributes have been deserialized. In particular, they're called
by `obj_tables.io.WorkbookReader.link_model`. Therefore, they get passed all objects that are not inline,
which can then be referenced to deserialize the related attribute.


:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-12-12
:Copyright: 2016, Karr Lab
:License: MIT
"""

from datetime import date, time, datetime
from enum import Enum
from itertools import chain
from math import isnan
from natsort import natsort_keygen, natsorted, ns
from operator import attrgetter
from stringcase import sentencecase
from os.path import basename, splitext
from weakref import WeakSet, WeakKeyDictionary
from wc_utils.util.list import det_dedupe
from wc_utils.util.misc import quote, OrderableNone
from wc_utils.util.ontology import are_terms_equivalent
from wc_utils.util.string import indent_forest
from wc_utils.util.types import get_subclasses, get_superclasses
from wc_utils.workbook.core import get_column_letter
import abc
import collections
import collections.abc
import copy
import dateutil.parser
import inflect
import json
import numbers
import pronto
import queue
import re
import sys
import validate_email
import warnings
import wc_utils.workbook.io
# todo: simplify primary attributes, deserialization
# todo: improve memory efficiency
# todo: improve run-time
# todo: improve naming: on meaning for Model, clean -> convert, Slug -> id, etc.

DOC_TABLE_TYPE = 'Data'
SCHEMA_TABLE_TYPE = 'Schema'
SCHEMA_SHEET_NAME = '_Schema'
TOC_TABLE_TYPE = 'TableOfContents'
TOC_SHEET_NAME = '_Table of contents'


class ModelMerge(int, Enum):
    """ Types of model merging operations """
    join = 1
    append = 2


class ModelMeta(type):

    def __new__(metacls, name, bases, namespace):
        """
        Args:
            metacls (:obj:`Model`): `Model`, or a subclass of `Model`
            name (:obj:`str`): `Model` class name
            bases (:obj:`tuple`): tuple of superclasses
            namespace (:obj:`dict`): namespace of `Model` class definition

        Returns:
            :obj:`Model`: a new instance of `Model`, or a subclass of `Model`
        """

        # terminate early so this method is only run on the subclasses of
        # `Model`
        if name == 'Model' and len(bases) == 1 and bases[0] is object:
            return super(ModelMeta, metacls).__new__(metacls, name, bases, namespace)

        # Create new Meta internal class if not provided in class definition so
        # that each model has separate internal Meta classes
        if 'Meta' not in namespace:
            Meta = namespace['Meta'] = type('Meta', (Model.Meta,), {})

            Meta.attribute_order = []
            for base in bases:
                if issubclass(base, Model):
                    for attr_name in base.Meta.attribute_order:
                        if attr_name not in Meta.attribute_order:
                            Meta.attribute_order.append(attr_name)
            Meta.attribute_order = tuple(Meta.attribute_order)

            Meta.unique_together = copy.deepcopy(bases[0].Meta.unique_together)
            Meta.indexed_attrs_tuples = copy.deepcopy(
                bases[0].Meta.indexed_attrs_tuples)
            Meta.description = bases[0].Meta.description
            Meta.table_format = bases[0].Meta.table_format
            Meta.frozen_columns = bases[0].Meta.frozen_columns
            Meta.ordering = copy.deepcopy(bases[0].Meta.ordering)
            Meta.children = copy.deepcopy(bases[0].Meta.children)
            Meta.merge = bases[0].Meta.merge

        # validate attribute inheritance
        metacls.validate_meta(name, bases, namespace)

        # validate attributes
        metacls.validate_attributes(name, bases, namespace)
        metacls.validate_related_attributes(name, bases, namespace)

        # validate primary attribute
        metacls.validate_primary_attribute(name, bases, namespace)

        # validate attribute inheritance
        metacls.validate_attribute_inheritance(name, bases, namespace)

        # call super class method
        cls = super(ModelMeta, metacls).__new__(metacls, name, bases, namespace)

        # Initialize meta data
        metacls.init_inheritance(cls)

        metacls.init_attributes(cls)

        metacls.init_primary_attribute(cls)

        cls.Meta.related_attributes = collections.OrderedDict()
        cls.Meta.local_attributes = collections.OrderedDict()
        for attr in cls.Meta.attributes.values():
            cls.Meta.local_attributes[attr.name] = LocalAttribute(attr, cls)
        for model in get_subclasses(Model):
            metacls.init_related_attributes(cls, model)
        metacls.init_attribute_order(cls)

        metacls.init_ordering(cls)

        metacls.normalize_attr_tuples(cls, 'unique_together')
        metacls.normalize_attr_tuples(cls, 'indexed_attrs_tuples')

        metacls.init_verbose_names(cls)

        metacls.create_model_manager(cls)

        # Return new class
        return cls

    @classmethod
    def validate_meta(metacls, name, bases, namespace):
        reserved_names = [
            TOC_SHEET_NAME,
            SCHEMA_SHEET_NAME,
        ]

        if namespace['Meta'].verbose_name in reserved_names:
            raise ValueError('Verbose name for {} cannot be {}, '
                             'which is reserved for the table of contents'.format(
                                 name, ', '.join('"' + n + '"' for n in reserved_names)))

        if namespace['Meta'].verbose_name_plural in reserved_names:
            raise ValueError('Plural verbose name for {} cannot be {}, '
                             'which is reserved for the table of contents'.format(
                                 name, ', '.join('"' + n + '"' for n in reserved_names)))

    @classmethod
    def validate_attributes(metacls, name, bases, namespace):
        """ Validate attribute values

        Raises:
            :obj:`ValueError`: if attributes are not valid
        """
        if '_{}__type'.format(name) in namespace:
            raise ValueError('Attribute cannot have reserved name `__type`')

        if '_{}__id'.format(name) in namespace:
            raise ValueError('Attribute cannot have reserved name `__id`')

        if not isinstance(namespace['Meta'].attribute_order, (tuple, list)):
            raise ValueError('`{}.Meta.attribute_order` must be a tuple of strings of the names of attributes of {}'.format(name, name))

        for attr_name in namespace['Meta'].attribute_order:
            if not isinstance(attr_name, str):
                raise ValueError("`{}.Meta.attribute_order` must be a tuple of strings of the names of attributes of {}; "
                                 "'{}' is not a string".format(
                                     name, name, attr_name))

            if attr_name not in namespace:
                is_attr = False
                for base in bases:
                    if hasattr(base, attr_name):
                        is_attr = True

                if not is_attr:
                    raise ValueError("`{}.Meta.attribute_order` must be a tuple of strings of the names of attributes of {}; "
                                     "{} does not have an attribute with name '{}'".format(
                                         name, name, name, attr_name))

        metacls.validate_attr_tuples(name, bases, namespace, 'unique_together')
        metacls.validate_attr_tuples(name, bases, namespace, 'indexed_attrs_tuples')

    @classmethod
    def validate_attr_tuples(metacls, name, bases, namespace, meta_attribute_name):
        """ Validate a tuple of tuples of attribute names

        Args:
            meta_attribute_name (:obj:`str`): the name of the attribute to validate and normalize

        Raises:
            :obj:`ValueError`: if attributes are not valid
        """
        # getattr(namespace['Meta'], meta_attribute_name) should be a tuple of tuples of
        # attribute names

        meta_attribute = getattr(namespace['Meta'], meta_attribute_name)

        attribute_names = []
        for attr_name, attr in namespace.items():
            if isinstance(attr, Attribute):
                attribute_names.append(attr_name)
        for base in bases:
            if issubclass(base, Model) and base.Meta.attributes:
                attribute_names += base.Meta.attributes.keys()

        for model in get_subclasses(Model):
            for attr in model.Meta.attributes.values():
                if isinstance(attr, RelatedAttribute):
                    if isinstance(attr.related_class, str):
                        related_class_name = attr.related_class
                        if '.' not in related_class_name:
                            related_class_name = model.__module__ + '.' + related_class_name
                    else:
                        related_class_name = attr.related_class.__module__ + \
                            '.' + attr.related_class.__name__

                    if attr.name in model.__dict__ and attr.related_name:
                        if '__module__' in namespace and related_class_name == namespace['__module__'] + '.' + name:
                            attribute_names.append(attr.related_name)
                        else:
                            for base in bases:
                                if related_class_name == base.__module__ + '.' + base.__name__:
                                    attribute_names.append(attr.related_name)
                                    break

        if not isinstance(meta_attribute, tuple):
            raise ValueError("{} for '{}' must be a tuple, not '{}'".format(
                meta_attribute_name, name, meta_attribute))

        for tup_of_attrnames in meta_attribute:
            if not isinstance(tup_of_attrnames, tuple):
                raise ValueError("{} for '{}' must be a tuple of tuples, not '{}'".format(
                    meta_attribute_name, name, meta_attribute))

            for attr_name in tup_of_attrnames:
                if not isinstance(attr_name, str):
                    raise ValueError("{} for '{}' must be a tuple of tuples of strings, not '{}'".format(
                        meta_attribute_name, name, meta_attribute))

                if attr_name not in attribute_names:
                    raise ValueError("{} for '{}' must be a tuple of tuples of attribute names, not '{}'".format(
                        meta_attribute_name, name, meta_attribute))

            if len(set(tup_of_attrnames)) < len(tup_of_attrnames):
                raise ValueError("{} for '{}' cannot repeat attribute names "
                                 "in any tuple: '{}'".format(meta_attribute_name, name, meta_attribute))

        # raise errors if multiple tup_of_attrnames are equivalent
        tup_of_attrnames_map = collections.defaultdict(list)
        for tup_of_attrnames in meta_attribute:
            tup_of_attrnames_map[
                frozenset(tup_of_attrnames)].append(tup_of_attrnames)
        equivalent_tuples = []
        for equivalent_tup_of_attrnames in tup_of_attrnames_map.values():
            if 1 < len(equivalent_tup_of_attrnames):
                equivalent_tuples.append(equivalent_tup_of_attrnames)
        if 0 < len(equivalent_tuples):
            raise ValueError("{} cannot contain identical attribute sets: {}".format(
                meta_attribute_name, str(equivalent_tuples)))

    # enable suspension of checking of same related attribute name so that obj_tables schemas can be migrated
    CHECK_SAME_RELATED_ATTRIBUTE_NAME = True

    @classmethod
    def validate_related_attributes(metacls, name, bases, namespace):
        """ Check the related attributes

        Raises:
            :obj:`ValueError`: if an :obj:`OneToManyAttribute` or :obj:`ManyToOneAttribute` has a `related_name` equal to its `name`
        """
        for attr_name, attr in namespace.items():
            if isinstance(attr, (OneToManyAttribute, ManyToOneAttribute)) and attr.related_name == attr_name:
                raise ValueError('The related name of {} {} cannot be equal to its name'.format(
                    attr.__class__.__name__, attr_name))

        for attr_name, attr in namespace.items():
            if isinstance(attr, RelatedAttribute):

                # deserialize related class references by class name
                if isinstance(attr.related_class, str):
                    related_class_name = attr.related_class
                    if '.' not in related_class_name:
                        related_class_name = namespace.get(
                            '__module__', '') + '.' + related_class_name

                    related_class = get_model(related_class_name)
                else:
                    related_class = attr.related_class

                # setup related attributes on related classes
                if attr_name in namespace and attr.related_name and \
                        isinstance(related_class, type) and issubclass(related_class, Model):
                    related_classes = chain(
                        [related_class], get_subclasses(related_class))
                    for related_class in related_classes:
                        # check that name doesn't conflict with another
                        # attribute
                        if attr.related_name in related_class.Meta.attributes and \
                                not (isinstance(attr, (OneToOneAttribute, ManyToManyAttribute)) and attr.related_name == attr_name):
                            other_attr = related_class.Meta.attributes[
                                attr.related_name]
                            raise ValueError('Related attribute {}.{} cannot use the same related name as {}.{}'.format(
                                name, attr_name,
                                related_class.__name__, attr.related_name,
                            ))

                        # check that name doesn't clash with another related
                        # attribute from a different model
                        if metacls.CHECK_SAME_RELATED_ATTRIBUTE_NAME and \
                                attr.related_name in related_class.Meta.related_attributes and \
                                related_class.Meta.related_attributes[attr.related_name] is not attr:
                            other_attr = related_class.Meta.related_attributes[
                                attr.related_name]
                            raise ValueError('Attributes {}.{} and {}.{} cannot use the same related attribute name {}.{}'.format(
                                name, attr_name,
                                other_attr.primary_class.__name__, other_attr.name,
                                related_class.__name__, attr.related_name,
                            ))

    @classmethod
    def validate_primary_attribute(metacls, name, bases, namespace):
        """ Check the attributes

        Raises:
            :obj:`ValueError`: if there are multiple primary attributes
        """
        num_primary_attributes = 0
        for attr_name, attr in namespace.items():
            if isinstance(attr, Attribute) and attr.primary:
                num_primary_attributes += 1

        if num_primary_attributes > 1:
            raise ValueError('Model {} cannot have more than one primary attribute'.format(
                metacls.__name__))  # pragma: no cover

    @classmethod
    def validate_attribute_inheritance(metacls, name, bases, namespace):
        """ Check attribute inheritance

        Raises:
            :obj:`ValueError`: if subclass overrides a superclass attribute (instance of Attribute) with an incompatible
                attribute (i.e. an attribute that is not a subclass of the class of the super class' attribute)
        """
        for attr_name, attr in namespace.items():
            for super_cls in bases:
                if attr_name in dir(super_cls):
                    super_attr = getattr(super_cls, attr_name)
                    if (isinstance(attr, Attribute) or isinstance(super_attr, Attribute)) and not isinstance(attr, super_attr.__class__):
                        raise ValueError(('Attribute "{}" of class "{}" inherited from "{}" must be a subclass of {} '
                                          'because the attribute is already defined in the superclass').
                                         format(__name__, super_cls.__name__, attr_name, super_attr.__class__.__name__))

    def init_inheritance(cls):
        """ Create tuple of this model and superclasses which are subclasses of `Model` """
        cls.Meta.inheritance = tuple([cls] + [supercls for supercls in get_superclasses(cls)
                                              if issubclass(supercls, Model) and supercls is not Model])

    def init_attributes(cls):
        """ Initialize attributes """

        cls.Meta.attributes = collections.OrderedDict()
        for attr_name in sorted(dir(cls)):
            orig_attr = getattr(cls, attr_name)

            if isinstance(orig_attr, Attribute):
                if attr_name in cls.__dict__:
                    attr = orig_attr
                else:
                    attr = copy.copy(orig_attr)

                attr.name = attr_name
                if not attr.verbose_name:
                    attr.verbose_name = sentencecase(attr_name)
                cls.Meta.attributes[attr_name] = attr

                if isinstance(attr, RelatedAttribute) and attr.name in cls.__dict__:
                    attr.primary_class = cls

    def init_related_attributes(cls, model_cls):
        """ Initialize related attributes """
        for attr in model_cls.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute):

                # deserialize related class references by class name
                if isinstance(attr.related_class, str):
                    related_class_name = attr.related_class
                    if '.' not in related_class_name:
                        related_class_name = model_cls.__module__ + '.' + related_class_name

                    related_class = get_model(related_class_name)
                    if related_class:
                        attr.related_class = related_class
                        model_cls.Meta.local_attributes[attr.name].related_class = related_class

                # setup related attributes on related classes
                if attr.name in model_cls.__dict__ and attr.related_name and \
                        isinstance(attr.related_class, type) and issubclass(attr.related_class, Model):
                    related_classes = chain(
                        [attr.related_class], get_subclasses(attr.related_class))
                    for related_class in related_classes:
                        # add attribute to dictionary of related attributes
                        related_class.Meta.related_attributes[
                            attr.related_name] = attr
                        related_class.Meta.local_attributes[attr.related_name] = LocalAttribute(
                            attr, related_class, is_primary=False)

    def init_primary_attribute(cls):
        """ Initialize the primary attribute of a model """
        primary_attributes = [
            attr for attr in cls.Meta.attributes.values() if attr.primary]

        if len(primary_attributes) == 0:
            cls.Meta.primary_attribute = None

        elif len(primary_attributes) == 1:
            cls.Meta.primary_attribute = primary_attributes[0]

        else:
            # unreachable because covered by above validation
            pass  # pragma: no cover

    def init_attribute_order(cls):
        """ Initialize the order in which the attributes should be printed across Excel columns """
        cls.Meta.attribute_order = tuple(cls.Meta.attribute_order) or ()

    def init_ordering(cls):
        """ Initialize how to sort objects """
        if not cls.Meta.ordering:
            if cls.Meta.primary_attribute:
                cls.Meta.ordering = (cls.Meta.primary_attribute.name, )
            else:
                cls.Meta.ordering = ()

    def init_verbose_names(cls):
        """ Initialize the singular and plural verbose names of a model """
        if not cls.Meta.verbose_name:
            cls.Meta.verbose_name = sentencecase(cls.__name__)

            if not cls.Meta.verbose_name_plural:
                inflect_engine = inflect.engine()
                cls.Meta.verbose_name_plural = sentencecase(
                    inflect_engine.plural(cls.__name__))

        elif not cls.Meta.verbose_name_plural:
            inflect_engine = inflect.engine()
            cls.Meta.verbose_name_plural = inflect_engine.plural(
                cls.Meta.verbose_name)

    def normalize_attr_tuples(cls, attribute):
        """ Normalize a tuple of tuples of attribute names

        Args:
            attribute (:obj:`str`): the name of the attribute to validate and normalize
        """

        # Normalize each tup_of_attrnames as a sorted tuple
        setattr(cls.Meta, attribute,
                ModelMeta.normalize_tuple_of_tuples_of_attribute_names(getattr(cls.Meta, attribute)))

    @staticmethod
    def normalize_tuple_of_tuples_of_attribute_names(tuple_of_tuples_of_attribute_names):
        """ Normalize a tuple of tuples of attribute names by sorting each member tuple

        Enables simple indexing and searching of tuples

        Args:
            tuple_of_tuples_of_attribute_names (:obj:`tuple`): a tuple of tuples of attribute names

        Returns:
            :obj:`tuple`: a tuple of sorted tuples of attribute names
        """
        normalized_tup_of_attrnames = []
        for tup_of_attrnames in tuple_of_tuples_of_attribute_names:
            normalized_tup_of_attrnames.append(tuple(sorted(tup_of_attrnames)))
        return tuple(normalized_tup_of_attrnames)

    def create_model_manager(cls):
        """ Create a :obj:`Manager` for this :obj:`Model`

        The `Manager` is accessed via a `Model`'s `objects` attribute

        Args:
            cls (:obj:`type`): the :obj:`Model` class which is being managed
        """
        setattr(cls, 'objects', Manager(cls))


class Manager(object):
    """ Enable O(1) dictionary-based searching of a Model's instances

    This class is inspired by Django's `Manager` class. An instance of :obj:`Manger` is associated with
    each :obj:`Model` and accessed as the class attribute `objects` (as in Django).
    The tuples of attributes to index are specified by the `indexed_attrs_tuples` attribute of
    `core.Model.Meta`, which contains a tuple of tuples of attributes to index.
    :obj:`Model`\ s with empty `indexed_attrs_tuples` attributes incur no overhead from `Manager`.

    :obj:`Manager` maintains a dictionary for each indexed attribute tuple, and a reverse index from each
    :obj:`Model` instance to its indexed attribute tuple keys.

    These data structures support
    * O(1) get operations for `Model` instances indexed by a indexed attribute tuple
    * O(1) `Model` instance insert and update operations

    Attributes:
        cls (:obj:`class`): the :obj:`Model` class which is being managed
        _new_instances (:obj:`WeakSet`): set of all new instances of `cls` that have not been indexed,
            stored as weakrefs, so `Model`'s that are otherwise unused can be garbage collected
        _index_dicts (:obj:`dict` mapping `tuple` to :obj:`WeakSet`): indices that enable
            lookup of :obj:`Model` instances from their `Meta.indexed_attrs_tuples`
            mapping: <attr names tuple> -> <attr values tuple> -> WeakSet(<model_obj instances>)
        _reverse_index (:obj:`WeakKeyDictionary` mapping :obj:`Model` instance to :obj:`dict`): a reverse
            index that provides all of each :obj:`Model`'s indexed attribute tuple keys
            mapping: <model_obj instances> -> <attr names tuple> -> <attr values tuple>
        num_ops_since_gc (:obj:`int`): number of operations since the last gc of weaksets
    """
    # todo: learn how to describe dict -> dict -> X in Sphinx
    # todo: index computed attributes which don't take arguments
    # implement by modifying _get_attr_tuple_vals & using inspect.getcallargs()
    # todo: make Managers local, rather than global, by associating them with a Model collection, and
    # searching them through the collection; associate with a collection via a weakref so that when
    # the collection goes out of scope the Managers are gc'ed

    # number of Manager operations between calls to _gc_weaksets
    # todo: make this value configurable
    GC_PERIOD = 1000

    def __init__(self, cls):
        """
        Args:
            cls (:obj:`class`): the :obj:`Model` class which is being managed
        """
        self.cls = cls
        if self.cls.Meta.indexed_attrs_tuples:
            self._new_instances = WeakSet()
            self._create_indices()
            self.num_ops_since_gc = 0

    def _check_model(self, model_obj, method):
        """ Verify `model_obj`'s `Model`

        Args:
            model_obj (:obj:`Model`): a `Model` instance
            method (:obj:`str`): the name of the method requesting the check

        Raises:
            :obj:`ValueError`: if `model_obj`'s type is not handled by this `Manager`
            :obj:`ValueError`: if `model_obj`'s type does not have any indexed attribute tuples
        """
        if not type(model_obj) is self.cls:
            raise ValueError("{}(): The '{}' Manager does not process '{}' objects".format(
                method, self.cls.__name__, type(model_obj).__name__))
        if not self.cls.Meta.indexed_attrs_tuples:
            raise ValueError("{}(): The '{}' Manager does not have any indexed attribute tuples".format(
                method, self.cls.__name__))

    def _create_indices(self):
        """ Create dicts needed to manage indices on attribute tuples

        The references to :obj:`Model` instances are stored as weakrefs in a :obj:`WeakKeyDictionary`,
        so that :obj:`Model`'s which are otherwise unused get garbage collected.
        """
        self._index_dicts = {}
        # for each indexed_attrs, create a dict
        for indexed_attrs in self.cls.Meta.indexed_attrs_tuples:
            self._index_dicts[indexed_attrs] = {}

        # A reverse index from Model instances to index keys enables updates of instances that
        # are already indexed. Update is performed by deleting and inserting.
        self._reverse_index = WeakKeyDictionary()

    def _dump_index_dicts(self, file=None):
        """ Dump the index dictionaries for debugging

        Args:
            file (:obj:`object`, optitonal): an object with a `write(string)` method
        """
        # gc before printing to produce consistent data
        self._gc_weaksets()
        print("Dicts for '{}':".format(self.cls.__name__), file=file)
        for attr_tuple, d in self._index_dicts.items():
            print('\tindexed attr tuple:', attr_tuple, file=file)
            for k, v in d.items():
                print('\t\tk,v', k, {id(obj_tables)
                                     for obj_tables in v}, file=file)
        print("Reverse dicts for '{}':".format(self.cls.__name__), file=file)
        for obj, attr_keys in self._reverse_index.items():
            print("\tmodel at {}".format(id(obj)), file=file)
            for indexed_attrs, vals in attr_keys.items():
                print("\t\t'{}' is '{}'".format(
                    indexed_attrs, vals), file=file)

    @staticmethod
    def _get_attr_tuple_vals(model_obj, attr_tuple):
        """ Provide the values of the attributes in `attr_tuple`

        Args:
            model_obj (:obj:`Model`): a `Model` instance
            attr_tuple (:obj:`tuple`): a tuple of attribute names in `model_obj`

        Returns:
            :obj:`tuple`: `model_obj`'s values for the attributes in `attr_tuple`
        """
        return tuple(map(lambda name: getattr(model_obj, name), attr_tuple))

    @staticmethod
    def _get_hashable_values(values):
        """ Provide hashable values for a tuple of values of a `Model`'s attributes

        Args:
            values (:obj:`tuple`): values of `Model` attributes

        Returns:
            :obj:`tuple`: hashable values for a `tuple` of values of `Model` attributes

        Raises:
            :obj:`ValueError`: the `values` is not an iterable or is a string
        """
        if isinstance(values, str):
            raise ValueError(
                "_get_hashable_values does not take a string: '{}'".format(values))
        if not isinstance(values, collections.abc.Iterable):
            raise ValueError(
                "_get_hashable_values takes an iterable, not: '{}'".format(values))
        hashable_values = []
        for val in values:
            if isinstance(val, RelatedManager):
                hashable_values.append(
                    tuple(sorted([id(sub_val) for sub_val in val])))
            elif isinstance(val, Model):
                hashable_values.append(id(val))
            else:
                hashable_values.append(val)
        return tuple(hashable_values)

    @staticmethod
    def _hashable_attr_tup_vals(model_obj, attr_tuple):
        """ Provide hashable values for the attributes in `attr_tuple`

        Args:
            model_obj (:obj:`Model`): a `Model` instance
            attr_tuple (:obj:`tuple`): a tuple of attribute names in `model_obj`

        Returns:
            :obj:`tuple`: hashable values for `model_obj`'s attributes in `attr_tuple`
        """
        return Manager._get_hashable_values(Manager._get_attr_tuple_vals(model_obj, attr_tuple))

    def _get_attribute_types(self, model_obj, attr_names):
        """ Provide the attribute types for a tuple of attribute names

        Args:
            model_obj (:obj:`Model`): a `Model` instance
            attr_names (:obj:`tuple`): a tuple of attribute names in `model_obj`

        Returns:
            :obj:`tuple`: `model_obj`'s attribute types for the attribute name(s) in `attr_names`

        Raises:
            :obj:`ValueError`: `attr_names` is not an iterable or is a string or contains a string that
                is not a valid attribute name
        """
        self._check_model(model_obj, '_get_attribute_types')
        if isinstance(attr_names, str):
            raise ValueError(
                "_get_attribute_types(): attr_names cannot be a string: '{}'".format(attr_names))
        if not isinstance(attr_names, collections.abc.Iterable):
            raise ValueError(
                "_get_attribute_types(): attr_names must be an iterable, not: '{}'".format(attr_names))
        cls = self.cls
        types = []
        for attr_name in attr_names:
            if attr_name in cls.Meta.attributes:
                attr = cls.Meta.attributes[attr_name]
            elif attr_name in cls.Meta.related_attributes:
                attr = cls.Meta.related_attributes[attr_name]
            else:
                raise ValueError("Cannot find '{}' in attribute names for '{}'".format(attr_name,
                                                                                       cls.__name__))
            types.append(attr)
        return tuple(types)

    def _register_obj(self, model_obj):
        """ Register the `Model` instance `model_obj`

        Called by `Model.__init__()`. Do nothing if `model_obj`'s `Model` has no indexed attribute tuples.

        Args:
            model_obj (:obj:`Model`): a new `Model` instance
        """
        if self.cls.Meta.indexed_attrs_tuples:
            self._check_model(model_obj, '_register_obj')
            self._run_gc_weaksets()
            self._new_instances.add(model_obj)

    def _update(self, model_obj):
        """ Update the indices for `model_obj`, whose indexed attribute have been updated

        Costs O(I) where I is the number of indexed attribute tuples for `model_obj`.

        Args:
            model_obj (:obj:`Model`): a `Model` instance

        Raises:
            :obj:`ValueError`: `model_obj` is not in `_reverse_index`
        """
        self._check_model(model_obj, '_update')
        self._run_gc_weaksets()
        cls = self.cls
        if model_obj not in self._reverse_index:
            raise ValueError("Can't _update an instance of '{}' that is not in the _reverse_index".format(
                cls.__name__))
        self._delete(model_obj)
        self._insert(model_obj)

    def _delete(self, model_obj):
        """ Delete an `model_obj` from the indices

        Args:
            model_obj (:obj:`Model`): a `Model` instance
        """
        self._check_model(model_obj, '_delete')
        for indexed_attr_tuple, vals in self._reverse_index[model_obj].items():
            if vals in self._index_dicts[indexed_attr_tuple]:
                self._index_dicts[indexed_attr_tuple][vals].remove(model_obj)
                # Recover memory by deleting empty WeakSets.
                # Empty WeakSets formed by automatic removal of weak refs are
                # gc'ed by _gc_weaksets.
                if 0 == len(self._index_dicts[indexed_attr_tuple][vals]):
                    del self._index_dicts[indexed_attr_tuple][vals]
        del self._reverse_index[model_obj]

    def _insert_new(self, model_obj):
        """ Insert a new `model_obj` into the indices that are used to search on indexed attribute tuples

        Args:
            model_obj (:obj:`Model`): a `Model` instance

        Raises:
            :obj:`ValueError`: `model_obj` is not in `_new_instances`
        """
        self._check_model(model_obj, '_insert_new')
        if model_obj not in self._new_instances:
            raise ValueError(
                "Cannot _insert_new() an instance of '{}' that is not new".format(self.cls.__name__))
        self._insert(model_obj)
        self._new_instances.remove(model_obj)

    def _insert(self, model_obj):
        """ Insert `model_obj` into the indices that are used to search on indexed attribute tuples

        Costs O(I) where I is the number of indexed attribute tuples for the `Model`.

        Args:
            model_obj (:obj:`Model`): a `Model` instance
        """
        self._check_model(model_obj, '_insert')
        self._run_gc_weaksets()
        cls = self.cls

        for indexed_attr_tuple in cls.Meta.indexed_attrs_tuples:
            vals = Manager._hashable_attr_tup_vals(
                model_obj, indexed_attr_tuple)
            if vals not in self._index_dicts[indexed_attr_tuple]:
                self._index_dicts[indexed_attr_tuple][vals] = WeakSet()
            self._index_dicts[indexed_attr_tuple][vals].add(model_obj)

        d = {}
        for indexed_attr_tuple in cls.Meta.indexed_attrs_tuples:
            d[indexed_attr_tuple] = Manager._hashable_attr_tup_vals(
                model_obj, indexed_attr_tuple)
        self._reverse_index[model_obj] = d

    def _run_gc_weaksets(self):
        """ Periodically garbage collect empty WeakSets

        Returns:
            :obj:`int`: number of empty WeakSets deleted
        """
        self.num_ops_since_gc += 1
        if Manager.GC_PERIOD <= self.num_ops_since_gc:
            self.num_ops_since_gc = 0
            return self._gc_weaksets()
        return 0

    def _gc_weaksets(self):
        """ Garbage collect empty WeakSets formed by deletion of weak refs to `Model` instances with no strong refs

        Returns:
            :obj:`int`: number of empty WeakSets deleted
        """
        num = 0
        for indexed_attr_tuple, attr_val_dict in self._index_dicts.items():
            # do not change attr_val_dict while iterating
            attr_val_weakset_pairs = list(attr_val_dict.items())
            for attr_val, weakset in attr_val_weakset_pairs:
                if not weakset:
                    del self._index_dicts[indexed_attr_tuple][attr_val]
                    num += 1
        return num

    # Public Manager() methods follow
    # If the Model is not indexed these methods do nothing (and return None if
    # a value is returned)
    def reset(self):
        """ Reset this `Manager`

        Empty `Manager`'s indices. Since `Manager` globally indexes all instances of a `Model`,
        this method is useful when multiple models are loaded sequentially.
        """
        self.__init__(self.cls)

    def all(self):
        """ Provide all instances of the `Model` managed by this `Manager`

        Returns:
            :obj:`list` of :obj:`Model`: a list of all instances of the managed `Model`
            or `None` if the `Model` is not indexed
        """
        if self.cls.Meta.indexed_attrs_tuples:
            self._run_gc_weaksets()
            # return list of strong refs, so keys in WeakKeyDictionary cannot be changed by gc
            # while iterating over them
            return list(self._reverse_index.keys())
        else:
            return None

    def upsert(self, model_obj):
        """ Update the indices for `model_obj` that are used to search on indexed attribute tuples

        `Upsert` means update or insert. Update the indices if `model_obj` is already stored, otherwise
        insert `model_obj`. Users of `Manager` are responsible for calling this method if `model_obj`
        changes.

        Costs O(I) where I is the number of indexed attribute tuples for the `Model`.

        Args:
            model_obj (:obj:`Model`): a `Model` instance
        """
        if self.cls.Meta.indexed_attrs_tuples:
            if model_obj in self._new_instances:
                self._insert_new(model_obj)
            else:
                self._update(model_obj)

    def upsert_all(self):
        """ Upsert the indices for all of this `Manager`'s `Model`'s
        """
        if self.cls.Meta.indexed_attrs_tuples:
            for model_obj in self.all():
                self.upsert(model_obj)

    def insert_all_new(self):
        """ Insert all new instances of this `Manager`'s `Model`'s into the search indices
        """
        if self.cls.Meta.indexed_attrs_tuples:
            for model_obj in self._new_instances:
                self._insert(model_obj)
            self._new_instances.clear()

    def clear_new_instances(self):
        """ Clear the set of new instances that have not been inserted
        """
        if self.cls.Meta.indexed_attrs_tuples:
            self._new_instances.clear()

    def get(self, **kwargs):
        """ Get the `Model` instance(s) that match the attribute name,value pair(s) in `kwargs`

        The keys in `kwargs` must correspond to an entry in the `Model`'s `indexed_attrs_tuples`.
        Warning: this method is non-deterministic. To obtain `Manager`'s O(1) performance, `Model`
        instances in the index are stored in `WeakSet`'s. Therefore, the order of elements in the list
        returned is not reproducible. Applications that need reproducibility must deterministically
        order elements in lists returned by this method.

        Args:
            **kwargs: keyword args mapping from attribute name(s) to value(s)

        Returns:
            :obj:`list` of :obj:`Model`: a list of `Model` instances whose indexed attribute tuples have the
            values in `kwargs`; otherwise `None`, indicating no match

        Raises:
            :obj:`ValueError`: if no arguments are provided, or the attribute name(s) in `kwargs.keys()`
            do not correspond to an indexed attribute tuple of the `Model`
        """
        cls = self.cls

        if 0 == len(kwargs.keys()):
            raise ValueError(
                "No arguments provided in get() on '{}'".format(cls.__name__))
        if not self.cls.Meta.indexed_attrs_tuples:
            return None

        # searching for an indexed_attrs instance
        # Sort by attribute names, to obtain the normalized order for attributes in an indexed_attrs_tuples.
        # This normalization is performed by
        # ModelMeta.normalize_tuple_of_tuples_of_attribute_names during
        # ModelMeta.__new__()
        keys, vals = zip(*sorted(kwargs.items()))
        possible_indexed_attributes = keys
        if possible_indexed_attributes not in self._index_dicts:
            raise ValueError("{} not an indexed attribute tuple in '{}'".format(possible_indexed_attributes,
                                                                                cls.__name__))
        if vals not in self._index_dicts[possible_indexed_attributes]:
            return None
        if 0 == len(self._index_dicts[possible_indexed_attributes][vals]):
            return None
        return list(self._index_dicts[possible_indexed_attributes][vals])

    def get_one(self, **kwargs):
        """ Get one `Model` instance that matches the attribute name,value pair(s) in `kwargs`

        Uses `get`.

        Args:
            **kwargs: keyword args mapping from attribute name(s) to value(s)

        Returns:
            `Model`: a `Model` instance whose indexed attribute tuples have the values in `kwargs`,
            or `None` if no `Model` satisfies the query

        Raises:
            :obj:`ValueError`: if `get` raises an exception, or if multiple instances match.
        """
        rv = self.get(**kwargs)
        cls = self.cls
        if rv is None:
            return None
        if 1 < len(rv):
            raise ValueError("get_one(): {} {} instances with '{}'".format(len(rv), cls.__name__,
                                                                           kwargs))
        return rv[0]


class TableFormat(Enum):
    """ Describes a table's orientation

    * `row`: the first row contains attribute names; subsequents rows store objects
    * `column`: the first column contains attribute names; subsequents columns store objects
    * `cell`: a cell contains a table, as a comma-separated list for example
    * `multiple_cells`: multiple cells within a row or column
    """
    row = 1
    column = 2
    cell = 3
    multiple_cells = 4


class Model(object, metaclass=ModelMeta):
    """ Base object model

    Attributes:
        _source (:obj:`ModelSource`): file location, worksheet, column, and row where the object was defined
        _comments (:obj:`list` of :obj:`str`): comments

    Class attributes:
        objects (:obj:`Manager`): a `Manager` that supports searching for `Model` instances
    """

    class Meta(object):
        """ Meta data for :class:`Model`

        Attributes:
            attributes (:obj:`collections.OrderedDict` of :obj:`str`, `Attribute`): attributes
            related_attributes (:obj:`collections.OrderedDict` of :obj:`str, `Attribute`): attributes
                declared in related objects
            local_attributes (:obj:`collections.OrderedDict` of :obj:`str`, :obj:`Attribute`): dictionary
                that maps the names of all local attributes to their instances, including attributes defined
                in this class and attributes defined in related classes
            primary_attribute (:obj:`Attribute`): attribute with `primary` = `True`
            unique_together (:obj:`tuple` of :obj:`tuple`'s of attribute names): controls what tuples of
                attribute values must be unique
            indexed_attrs_tuples (:obj:`tuple` of `tuple`'s of attribute names): tuples of attributes on
                which instances of this `Model` will be indexed by the `Model`'s `Manager`
            attribute_order (:obj:`tuple` of :obj:`str`): tuple of attribute names, in the order in which they should be displayed
            verbose_name (:obj:`str`): verbose name to refer to an instance of the model
            verbose_name_plural (:obj:`str`): plural verbose name for multiple instances of the model
            description (:obj:`str`): description of the model (e.g., to print in the table of contents in Excel)
            table_format (:obj:`TableFormat`): orientation of model objects in table (e.g. Excel)
            frozen_columns (:obj:`int`): number of Excel columns to freeze
            inheritance (:obj:`tuple` of `class`): tuple of all superclasses
            ordering (:obj:`tuple` of attribute names): controls the order in which objects should be printed when serialized
            children (:obj:`dict` that maps :obj:`str` to :obj:`tuple` of :obj:`str`): dictionary that maps types of children to
                names of attributes which compose each type of children
            merge (:obj:`ModelMerge`): type of merging operation
        """
        attributes = None
        related_attributes = None
        primary_attribute = None
        unique_together = ()
        indexed_attrs_tuples = ()
        attribute_order = ()
        verbose_name = ''
        verbose_name_plural = ''
        description = ''
        table_format = TableFormat.row
        frozen_columns = 1
        inheritance = None
        ordering = None
        children = {}
        merge = ModelMerge.join

    def __init__(self, _comments=None, **kwargs):
        """
        Args:
            **kwargs: dictionary of keyword arguments with keys equal to the names of the model attributes

        Raises:
            :obj:`TypeError`: if keyword argument is not a defined attribute
        """

        """ check that related classes of attributes are defined """
        self.validate_related_attributes()

        """ initialize attributes """
        # attributes
        for attr in self.Meta.attributes.values():
            super(Model, self).__setattr__(
                attr.name, attr.get_init_value(self))

        # related attributes
        for attr in self.Meta.related_attributes.values():
            super(Model, self).__setattr__(
                attr.related_name, attr.get_related_init_value(self))

        """ set attribute values """
        # attributes
        for attr in self.Meta.attributes.values():
            if attr.name not in kwargs:
                default = attr.get_default()
                setattr(self, attr.name, default)

        # attributes
        for attr in self.Meta.related_attributes.values():
            if attr.related_name not in kwargs:
                default = attr.get_related_default(self)
                if default:
                    setattr(self, attr.related_name, default)

        # process arguments
        for attr_name, val in kwargs.items():
            if attr_name not in self.Meta.attributes and attr_name not in self.Meta.related_attributes:
                raise TypeError("'{:s}' is an invalid keyword argument for {}.__init__".format(
                    attr_name, self.__class__.__name__))
            setattr(self, attr_name, val)

        self._source = None
        self._comments = _comments or []

        # register this Model instance with the class' Manager
        self.__class__.objects._register_obj(self)

    @classmethod
    def get_attrs(cls, type=None, forward=True, reverse=True):
        """ Get attributes of a type, optionally including attributes
        from related classes. By default, return all attributes.

        Args:
            type (:obj:`type` or :obj:`tuple` of :obj:`type`, optional):
                type of attributes to get
            forward (:obj:`bool`, optional): if :obj:`True`, include
                attributes from class
            reverse (:obj:`bool`, optional): if :obj:`True`, include
                attributes from related classes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of matching attributes
        """
        type = type or Attribute

        attrs_to_search = []
        if forward:
            attrs_to_search = chain(attrs_to_search, cls.Meta.attributes.items())
        if reverse:
            attrs_to_search = chain(attrs_to_search, cls.Meta.related_attributes.items())

        matching_attrs = {}
        for attr_name, attr in attrs_to_search:
            if isinstance(attr, type):
                matching_attrs[attr_name] = attr

        return matching_attrs

    @classmethod
    def get_literal_attrs(cls):
        """ Get literal attributes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of literal attributes
        """
        return cls.get_attrs(type=LiteralAttribute)

    @classmethod
    def get_related_attrs(cls, reverse=True):
        """ Get related attributes

        Args:
            reverse (:obj:`bool`, optional): if :obj:`True`, include
                attributes from related classes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of related attributes
        """
        return cls.get_attrs(type=RelatedAttribute, reverse=reverse)

    def get_attrs_by_val(self, type=None, reverse=True,
                         include=None, exclude=None):
        """ Get attributes whose type is `type` and values are
        in `include` and not `exclude`, optionally including attributes
        from related classes. By default, get all attributes.

        Args:
            type (:obj:`type` or :obj:`tuple` of :obj:`type`, optional):
                type of attributes to get
            reverse (:obj:`bool`, optional): if :obj:`True`, include
                attributes from related classes
            include (:obj:`list`, optional): list of values to filter for
            exclude (:obj:`list`, optional): list of values to filter out

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of matching attributes
        """
        include_nan = include is not None and next((True for i in include if isinstance(i, numbers.Number) and isnan(i)), False)
        exclude_nan = exclude is not None and next((True for e in exclude if isinstance(e, numbers.Number) and isnan(e)), False)
        matching_attrs = {}

        attrs_to_search = self.__class__.get_attrs(type=type, reverse=reverse)
        for attr_name, attr in attrs_to_search.items():
            value = getattr(self, attr_name)
            if (include is None or (value in include or
                                    (include_nan
                                     and (isinstance(value, numbers.Number)
                                          and isnan(value))))) and \
               (exclude is None or (value not in exclude
                                    and (not exclude_nan or not
                                         (isinstance(value, numbers.Number) and
                                          isnan(value))))):
                matching_attrs[attr_name] = attr
        return matching_attrs

    def get_empty_literal_attrs(self):
        """ Get empty (:obj:`None`, '', or NaN) literal attributes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of empty literal attributes
        """
        return self.get_attrs_by_val(type=LiteralAttribute,
                                     include=(None, '', float('nan')))

    def get_non_empty_literal_attrs(self):
        """ Get non-empty (:obj:`None`, '', or NaN) literal attributes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of non-empty literal attributes
        """
        return self.get_attrs_by_val(type=LiteralAttribute,
                                     exclude=(None, '', float('nan')))

    def get_empty_related_attrs(self, reverse=True):
        """ Get empty (:obj:`None` or []) related attributes

        Args:
            reverse (:obj:`bool`, optional): if :obj:`True`, include
                attributes from related classes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of empty related attributes
        """
        return self.get_attrs_by_val(type=RelatedAttribute,
                                     reverse=reverse,
                                     include=(None, []))

    def get_non_empty_related_attrs(self, reverse=True):
        """ Get non-empty (:obj:`None` or []) related attributes

        Args:
            reverse (:obj:`bool`, optional): if :obj:`True`, include
                attributes from related classes

        Returns:
            :obj:`dict` of :obj:`str`, :obj:`Attribute`: dictionary of the names and instances
                of non-empty related attributes
        """
        return self.get_attrs_by_val(type=RelatedAttribute,
                                     reverse=reverse,
                                     exclude=(None, []))

    @classmethod
    def get_attr_index(cls, attr):
        """ Get the index of an attribute within `Meta.attribute_order`

        Args:
            attr (:obj:`Attribute`): attribute

        Returns:
            :obj:`int`: index of attribute within `Meta.attribute_order`
        """
        flat_attr_order = cls.Meta.attribute_order
        if attr.name not in flat_attr_order:
            raise ValueError('{} not in `attribute_order` for {}'.format(attr.name, cls.__name__))
        return flat_attr_order.index(attr.name)

    @classmethod
    def validate_related_attributes(cls):
        """ Validate attribute values

        Raises:
            :obj:`ValueError`: if related attributes are not valid (e.g. if a class that is the subject of
                a relationship does not have a primary attribute)
        """

        for attr_name, attr in cls.Meta.attributes.items():
            if isinstance(attr, RelatedAttribute) and not (isinstance(attr.related_class, type) and issubclass(attr.related_class, Model)):
                raise ValueError('Related class {} of {}.{} must be defined'.format(
                    attr.related_class, attr.primary_class.__name__, attr_name))

        # tabular orientation
        if cls.Meta.table_format == TableFormat.cell:
            if len(cls.Meta.related_attributes) == 0:
                raise ValueError(
                    'Inline model "{}" should have at least one one-to-one or one-to-many attribute'.format(cls.__name__))

    def __setattr__(self, attr_name, value, propagate=True):
        """ Set attribute and validate any unique attribute constraints

        Args:
            attr_name (:obj:`str`): attribute name
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change through attribute `set_value` and `set_related_value`
        """
        if propagate:
            if attr_name in self.__class__.Meta.attributes:
                attr = self.__class__.Meta.attributes[attr_name]
                value = attr.set_value(self, value)

            elif attr_name in self.__class__.Meta.related_attributes:
                attr = self.__class__.Meta.related_attributes[attr_name]
                value = attr.set_related_value(self, value)

        super(Model, self).__setattr__(attr_name, value)

    @classmethod
    def get_nested_attr(cls, attr_path):
        """ Get the value of an attribute or a nested attribute of a model

        Args:
            attr_path (:obj:`list` of :obj:`list` of :obj:`str`):
                the path to an attribute or nested attribute of a model

        Returns:
            :obj:`Attribute`: nested attribute
        """

        if not isinstance(attr_path, (tuple, list)):
            attr_path = (attr_path,)

        # traverse to the final attribute
        value = cls
        for i_attr, attr in enumerate(attr_path):
            if isinstance(attr, (tuple, list)):
                if len(attr) == 1:
                    attr_name = attr[0]
                    attr_get_one_filter = None
                elif len(attr) == 2:
                    attr_name = attr[0]
                    attr_get_one_filter = attr[1]
                else:
                    raise ValueError('Attribute specification must be a string, 1-tuple, or 2-tuple')
            else:
                attr_name = attr
                attr_get_one_filter = None

            value = value.Meta.local_attributes[attr_name]
            if i_attr < len(attr_path) - 1 or attr_get_one_filter:
                value = value.related_class
            else:
                value = value.attr

        # return value
        return value

    def get_nested_attr_val(self, attr_path):
        """ Get the value of an attribute or a nested attribute of a model

        Args:
            attr_path (:obj:`list` of :obj:`list` of :obj:`object`):
                the path to an attribute or nested attribute of a model

        Returns:
            :obj:`Object`: value of the attribute or nested attribute
        """

        if not isinstance(attr_path, (tuple, list)):
            attr_path = (attr_path,)

        # traverse to the final attribute
        value = self
        for attr in attr_path:
            attr_name, attr_get_one_filter = self._parse_attr_path_el(attr)
            value = getattr(value, attr_name)
            if attr_get_one_filter:
                value = value.get_one(**attr_get_one_filter)

        # return value
        return value

    def set_nested_attr_val(self, attr_path, value):
        """ Set the value of an attribute or a nested attribute of a model

        Args:
            attr_path (:obj:`list` of :obj:`list` of :obj:`object`):
                the path to an attribute or nested attribute of a model
            value (:obj:`object`): new value

        Returns:
            :obj:`Model`: the same model with the value of an attribute
                modified
        """
        if not attr_path:
            raise ValueError('Attribute specification must be a string or tuple')

        if not isinstance(attr_path, (tuple, list)):
            attr_path = (attr_path,)

        # traverse to parent of final attribute
        nested_obj = self.get_nested_attr_val(attr_path[0:-1])

        # get name of final attribute
        attr = attr_path[-1]
        if isinstance(attr, (tuple, list)):
            if len(attr) == 1:
                attr_name = attr[0]
            else:
                raise ValueError('Specification of final attribute must be a string or 1-tuple')
        else:
            attr_name = attr

        # change value
        if hasattr(nested_obj, attr_name):
            setattr(nested_obj, attr_name, value)
        else:
            raise AttributeError("'{}' object has no attribute '{}'".format(nested_obj.__class__.__name__, attr_name))

        # return self
        return self

    @classmethod
    def are_attr_paths_equal(cls, attr_path, other_attr_path):
        """ Determine if two attribute paths are semantically equal

        Args:
            attr_path (:obj:`list` of :obj:`list` of :obj:`object`):
                the path to an attribute or nested attribute of a model
            other_attr_path (:obj:`list` of :obj:`list` of :obj:`object`):
                the path to another attribute or nested attribute of a model

        Returns:
            :obj:`bool`: :obj:`True` if the paths are semantically equal
        """
        if not isinstance(attr_path, (tuple, list)):
            attr_path = (attr_path,)
        if not isinstance(other_attr_path, (tuple, list)):
            other_attr_path = (other_attr_path,)

        # traverse over the path to the nested attribute
        if len(attr_path) != len(other_attr_path):
            return False

        for attr, other_attr in zip(attr_path, other_attr_path):
            attr_name, attr_get_one_filter = cls._parse_attr_path_el(attr)
            other_attr_name, other_attr_get_one_filter = cls._parse_attr_path_el(other_attr)

            if attr_name != other_attr_name:
                return False

            if attr_get_one_filter is None:
                if other_attr_get_one_filter is not None:
                    return False
            elif other_attr_get_one_filter is None:
                return False
            else:
                if set(attr_get_one_filter.keys()) != set(other_attr_get_one_filter.keys()):
                    return False
                for key in attr_get_one_filter.keys():
                    attr_val = attr_get_one_filter[key]
                    other_val = other_attr_get_one_filter[key]

                    if not (attr_val == other_val or (isinstance(attr_val, pronto.Term) and are_terms_equivalent(attr_val, other_val))):
                        return False

        return True

    @classmethod
    def _parse_attr_path_el(cls, attr):
        """ Parse an element of a path to a nested attribute

        Args:
            attr (:obj:`list` of :obj:`dict`): an element of a path to a nested attribute

        Returns:
            :obj:`str`: attribute name
            :obj:`dict`: filter for values of attribute

        Raises:
            :obj:`ValueError`: if the attribute specification is not valid
        """
        if isinstance(attr, (tuple, list)):
            if len(attr) == 1:
                attr_name = attr[0]
                attr_get_one_filter = None
            elif len(attr) == 2:
                attr_name = attr[0]
                attr_get_one_filter = attr[1]
            else:
                raise ValueError('Attribute specification must be a string, 1-tuple, or 2-tuple')
        else:
            attr_name = attr
            attr_get_one_filter = None

        return (attr_name, attr_get_one_filter)

    def normalize(self):
        """ Normalize an object into a canonical form. Specifically, this method sorts the RelatedManagers
        into a canonical order because their order has no semantic meaning. Importantly, this canonical form
        is reproducible. Thus, this canonical form facilitates reproducible computations on top of :obj:`Model`
        objects.
        """

        self._generate_normalize_sort_keys()

        normalized_objs = []
        objs_to_normalize = [self]

        while objs_to_normalize:
            obj = objs_to_normalize.pop()
            if obj not in normalized_objs:
                normalized_objs.append(obj)

                for attr_name, attr in chain(obj.Meta.attributes.items(), obj.Meta.related_attributes.items()):
                    if isinstance(attr, RelatedAttribute):
                        val = getattr(obj, attr_name)

                        # normalize children
                        if isinstance(val, list):
                            objs_to_normalize.extend(val)
                        elif val:
                            objs_to_normalize.append(val)

                        # sort
                        if isinstance(val, list) and len(val) > 1:
                            if attr_name in obj.Meta.attributes:
                                cls = attr.related_class
                            else:
                                cls = attr.primary_class

                            val.sort(key=cls._normalize_sort_key())

    @classmethod
    def _generate_normalize_sort_keys(cls):
        """ Generates keys for sorting the class """
        generated_keys = []
        keys_to_generate = [cls]
        while keys_to_generate:
            cls = keys_to_generate.pop()
            if cls not in generated_keys:
                generated_keys.append(cls)

                cls._normalize_sort_key = cls._generate_normalize_sort_key()

                for attr in cls.Meta.attributes.values():
                    if isinstance(attr, RelatedAttribute):
                        keys_to_generate.append(attr.related_class)

                for attr in cls.Meta.related_attributes.values():
                    if isinstance(attr, RelatedAttribute):
                        keys_to_generate.append(attr.primary_class)

    @classmethod
    def _generate_normalize_sort_key(cls):
        """ Generates key for sorting the class """

        # single unique attribute
        for attr_name, attr in cls.Meta.attributes.items():
            if attr.unique:
                return cls._generate_normalize_sort_key_unique_attr

        # tuple of attributes that are unique together
        if cls.Meta.unique_together:
            return cls._generate_normalize_sort_key_unique_together

        # include all attributes
        return cls._generate_normalize_sort_key_all_attrs

    @classmethod
    def _generate_normalize_sort_key_unique_attr(cls, processed_models=None):
        """ Generate a key for sorting models by their first unique attribute into a normalized order

        Args:
            processed_models (:obj:`list`, optional): list of models for which sort keys have already been generated

        Returns:
            :obj:`function`: key for sorting models by their first unique attribute into a normalized order
        """
        for attr_name, attr in cls.Meta.attributes.items():
            if attr.unique:
                break

        def key(obj):
            val = getattr(obj, attr_name)
            if val is None:
                return OrderableNone
            return val
        return key

    @classmethod
    def _generate_normalize_sort_key_unique_together(cls, processed_models=None):
        """ Generate a key for sorting models by their shortest set of unique attributes into a normalized order

        Args:
            processed_models (:obj:`list`, optional): list of models for which sort keys have already been generated

        Returns:
            :obj:`function`: key for sorting models by their shortest set of unique attributes into a normalized order
        """
        lens = [len(x) for x in cls.Meta.unique_together]
        i_shortest = lens.index(min(lens))
        attr_names = cls.Meta.unique_together[i_shortest]

        def key(obj):
            vals = []
            for attr_name in attr_names:
                val = getattr(obj, attr_name)
                if isinstance(val, RelatedManager):
                    vals.append(tuple([subval.serialize() for subval in val]))
                elif isinstance(val, Model):
                    vals.append(val.serialize())
                else:
                    vals.append(val)
            return tuple(vals)

        return key

    @classmethod
    def _generate_normalize_sort_key_all_attrs(cls, processed_models=None):
        """ Generate a key for sorting models by all of their attributes into a normalized order. This method should
        be used for models which do not have unique attributes or sets of unique attributes.

        Args:
            processed_models (:obj:`list`, optional): list of models for which sort keys have already been generated

        Returns:
            :obj:`function`: key for sorting models by all of their attributes into a normalized order
        """
        processed_models = copy.copy(processed_models) or []
        processed_models.append(cls)

        def key(obj, processed_models=processed_models):
            vals = []
            for attr_name in chain(cls.Meta.attributes.keys(), cls.Meta.related_attributes.keys()):
                val = getattr(obj, attr_name)
                if isinstance(val, RelatedManager):
                    if val.__class__ not in processed_models:
                        subvals_serial = []
                        for subval in val:
                            key = subval._normalize_sort_key(processed_models=processed_models)
                            subval_serial = key(subval)
                            subvals_serial.append(subval_serial)
                        vals.append(tuple(sorted(subvals_serial)))
                elif isinstance(val, Model):
                    if val.__class__ not in processed_models:
                        key_gen = val._normalize_sort_key
                        key = key_gen(processed_models=processed_models)
                        vals.append(key(val))
                else:
                    vals.append(OrderableNone if val is None else val)
            return tuple(vals)
        return key

    def is_equal(self, other, tol=0.):
        """ Determine whether two models are semantically equal

        Args:
            other (:obj:`Model`): object to compare
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: `True` if objects are semantically equal, else `False`
        """

        """
        todo: this can potentially be sped up by

        #. Flattening the object graphs
        #. Sorting the flattening object lists
        #. comparing the flattened lists item-by-item
        """

        self.normalize()
        other.normalize()

        checked_pairs = []
        pairs_to_check = [(self, other, )]
        while pairs_to_check:
            pair = pairs_to_check.pop()
            obj, other_obj = pair
            if pair not in checked_pairs:
                checked_pairs.append(pair)

                # non-related attributes
                if not obj._is_equal_attributes(other_obj, tol=tol):
                    return False

                # related attributes
                for attr_name, attr in chain(obj.Meta.attributes.items(), obj.Meta.related_attributes.items()):
                    if isinstance(attr, RelatedAttribute):
                        val = getattr(obj, attr_name)
                        other_val = getattr(other_obj, attr_name)

                        if val.__class__ != other_val.__class__:
                            return False

                        if val is None:
                            pass
                        elif isinstance(val, Model):
                            pairs_to_check.append((val, other_val, ))
                        elif len(val) != len(other_val):
                            return False  # pragma: no cover # unreachable because already checked by :obj:`_is_equal_attributes`
                        else:
                            for v, ov in zip(val, other_val):
                                pairs_to_check.append((v, ov, ))

        return True

    def _is_equal_attributes(self, other, tol=0.):
        """ Determine if the attributes of two objects are semantically equal

        Args:
            other (:obj:`Model`): object to compare
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: `True` if the objects' attributes are semantically equal, else `False`
        """
        # objects are the same
        if self is other:
            return True

        # check objects are of the same class
        if self.__class__ is not other.__class__:
            return False

        # check that their non-related attributes are semantically equal
        for attr_name, attr in chain(self.Meta.attributes.items(), self.Meta.related_attributes.items()):
            val = getattr(self, attr_name)
            other_val = getattr(other, attr_name)

            if not isinstance(attr, RelatedAttribute):
                if not attr.value_equal(val, other_val, tol=tol):
                    return False

            elif isinstance(val, RelatedManager):
                if len(val) != len(other_val):
                    return False

            else:
                if val is None and other_val is not None:
                    return False

        return True

    def __str__(self):
        """ Get the string representation of an object

        Returns:
            :obj:`str`: string representation of object
        """

        if self.__class__.Meta.primary_attribute:
            return '<{}.{}: {}>'.format(self.__class__.__module__,
                                        self.__class__.__name__,
                                        getattr(self, self.__class__.Meta.primary_attribute.name))

        return super(Model, self).__str__()

    def set_source(self, path_name, sheet_name, attribute_seq, row, table_id=None):
        """ Set metadata about source of the file, worksheet, columns, and row where the object was defined

        Args:
            path_name (:obj:`str`): pathname of source file for object
            sheet_name (:obj:`str`): name of spreadsheet containing source data for object
            attribute_seq (:obj:`list`): sequence of attribute names in source file; blank values
                indicate attributes that were ignored
            row (:obj:`int`): row number of object in its source file
            table_id (:obj:`str`, optional): id of the source table
        """
        self._source = ModelSource(path_name, sheet_name, attribute_seq, row, table_id=table_id)

    def get_source(self, attr_name):
        """ Get file location of attribute with name `attr_name`

        Provide the type, filename, worksheet, row, and column of `attr_name`. Row and column use
        1-based counting. Column is provided in Excel format if the file was a spreadsheet.

        Args:
            attr_name (:obj:`str`): attribute name

        Returns:
            tuple of (type, basename, worksheet, row, column)

        Raises:
            ValueError if the location of `attr_name` is unknown
        """
        if self._source is None:
            raise ValueError("{} was not loaded from a file".format(self.__class__.__name__))

        # account for the header row and possible transposition
        row = self._source.row
        try:
            column = self._source.attribute_seq.index(attr_name) + 1
        except ValueError:
            raise ValueError("{}.{} was not loaded from a file".format(self.__class__.__name__, attr_name))
        if self.Meta.table_format == TableFormat.column:
            column, row = row, column
        path = self._source.path_name
        sheet_name = self._source.sheet_name

        _, ext = splitext(path)
        ext = ext.split('.')[-1]
        if 'xlsx' in ext:
            col = excel_col_name(column)
            return (ext, quote(basename(path)), quote(sheet_name), row, col)
        else:
            return (ext, quote(basename(path)), quote(sheet_name), row, column)

    @classmethod
    def sort(cls, objects):
        """ Sort list of `Model` objects

        Args:
            objects (:obj:`list` of :obj:`Model`): list of objects

        Returns:
            :obj:`list` of :obj:`Model`: sorted list of objects
        """
        if cls.Meta.ordering:
            for attr_name in reversed(cls.Meta.ordering):
                if attr_name[0] == '-':
                    reverse = True
                    attr_name = attr_name[1:]
                else:
                    reverse = False
                objects.sort(key=natsort_keygen(key=lambda obj: cls.get_sort_key(obj, attr_name), alg=ns.IGNORECASE), reverse=reverse)

    @classmethod
    def get_sort_key(cls, object, attr_name):
        """ Get sort key for `Model` instance `object` based on `cls.Meta.ordering`

        Args:
            object (:obj:`Model`): `Model` instance
            attr_name (:obj:`str`): attribute name

        Returns:
            :obj:`object`: sort key for `object`
        """
        attr = cls.Meta.attributes[attr_name]
        return attr.serialize(getattr(object, attr_name))

    def difference(self, other, tol=0.):
        """ Get the semantic difference between two models

        Args:
            other (:obj:`Model`): other `Model`
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`str`: difference message
        """

        total_difference = {}
        checked_pairs = []
        pairs_to_check = [(self, other, total_difference)]
        while pairs_to_check:
            obj, other_obj, difference = pairs_to_check.pop()
            pair = (obj, other_obj, )

            if pair in checked_pairs:
                continue
            checked_pairs.append(pair)

            # initialize structure to store differences
            difference['objects'] = (obj, other_obj, )

            # types
            if obj.__class__ is not other_obj.__class__:
                difference['type'] = 'Objects {} and {} have different types "{}" and "{}"'.format(
                    obj, other_obj, obj.__class__, other_obj.__class__)
                continue

            # attributes
            difference['attributes'] = {}

            for attr_name, attr in chain(obj.Meta.attributes.items(), obj.Meta.related_attributes.items()):
                val = getattr(obj, attr_name)
                other_val = getattr(other_obj, attr_name)

                if not isinstance(attr, RelatedAttribute):
                    if not attr.value_equal(val, other_val, tol=tol):
                        difference['attributes'][
                            attr_name] = '{} != {}'.format(val, other_val)

                elif isinstance(val, RelatedManager):
                    if len(val) != len(other_val):
                        difference['attributes'][attr_name] = 'Length: {} != Length: {}'.format(
                            len(val), len(other_val))
                    else:
                        serial_vals = sorted(((v.serialize() or '', v)
                                              for v in val), key=lambda x: x[0])
                        serial_other_vals = sorted(
                            ((v.serialize() or '', v) for v in other_val), key=lambda x: x[0])

                        i_val = 0
                        oi_val = 0
                        difference['attributes'][attr_name] = []
                        while i_val < len(val) and oi_val < len(other_val):
                            serial_v = serial_vals[i_val][0]
                            serial_ov = serial_other_vals[oi_val][0]
                            if serial_v == serial_ov:
                                el_diff = {}
                                difference['attributes'][
                                    attr_name].append(el_diff)
                                pairs_to_check.append(
                                    (serial_vals[i_val][1], serial_other_vals[oi_val][1], el_diff))
                                i_val += 1
                                oi_val += 1
                            elif serial_v < serial_ov:
                                difference['attributes'][attr_name].append(
                                    'No matching element {}'.format(serial_v))
                                i_val += 1
                            else:
                                oi_val += 1

                        for i_val2 in range(i_val, len(val)):
                            difference['attributes'][attr_name].append(
                                'No matching element {}'.format(serial_vals[i_val2][0]))
                elif val is None:
                    if other_val is not None:
                        difference['attributes'][attr_name] = '{} != {}'.format(
                            val, other_val.serialize())
                elif other_val is None:
                    difference['attributes'][attr_name] = '{} != {}'.format(
                        val.serialize(), other_val)
                else:
                    difference['attributes'][attr_name] = {}
                    pairs_to_check.append(
                        (val, other_val, difference['attributes'][attr_name], ))

        return self._render_difference(self._simplify_difference(total_difference))

    def _simplify_difference(self, difference):
        """ Simplify difference data structure

        Args:
            difference (:obj:`dict`): representation of the semantic difference between two objects
        """

        to_flatten = [[difference, ], ]
        while to_flatten:
            diff_hierarchy = to_flatten.pop()
            if not diff_hierarchy:
                continue

            cur_diff = diff_hierarchy[-1]

            if not cur_diff:
                continue

            if 'type' in cur_diff:
                continue

            new_to_flatten = []
            flatten_again = False
            for attr, val in list(cur_diff['attributes'].items()):
                if isinstance(val, dict):
                    if val:
                        new_to_flatten.append(diff_hierarchy + [val])
                elif isinstance(val, list):
                    for v in reversed(val):
                        if v:
                            if isinstance(v, dict):
                                new_to_flatten.append(diff_hierarchy + [v])
                        else:
                            val.remove(v)
                            flatten_again = True

                if not val:
                    cur_diff['attributes'].pop(attr)
                    flatten_again = True

            if flatten_again:
                to_flatten.append(diff_hierarchy)
            if new_to_flatten:
                to_flatten.extend(new_to_flatten)

            if not cur_diff['attributes']:
                cur_diff.pop('attributes')
                cur_diff.pop('objects')

                to_flatten.append(diff_hierarchy[0:-1])

        return difference

    def _render_difference(self, difference):
        """ Generate string representation of difference data structure

        Args:
            difference (:obj:`dict`): representation of the semantic difference between two objects
        """
        msg = ''
        to_render = [[difference, 0, '']]
        while to_render:
            difference, indent, prefix = to_render.pop()

            msg += prefix

            if 'type' in difference:
                if indent:
                    msg += '\n' + ' ' * 2 * indent
                msg += difference['type']

            if 'attributes' in difference:
                if indent:
                    msg += '\n' + ' ' * 2 * indent
                msg += 'Objects ({}: "{}", {}: "{}") have different attribute values:'.format(
                    difference['objects'][0].__class__.__name__,
                    difference['objects'][0].serialize(),
                    difference['objects'][1].__class__.__name__,
                    difference['objects'][1].serialize(),
                )

                for attr_name in natsorted(difference['attributes'].keys(), alg=ns.IGNORECASE):
                    prefix = '\n{}`{}` are not equal:'.format(
                        ' ' * 2 * (indent + 1), attr_name)
                    if isinstance(difference['attributes'][attr_name], dict):
                        to_render.append(
                            [difference['attributes'][attr_name], indent + 2, prefix, ])

                    elif isinstance(difference['attributes'][attr_name], list):
                        new_to_render = []
                        new_to_msg = ''
                        for i_el, el_diff in enumerate(difference['attributes'][attr_name]):
                            if isinstance(el_diff, dict):
                                el_prefix = '\n{}element: {}: "{}" != element: {}: "{}"'.format(
                                    ' ' * 2 * (indent + 2),
                                    el_diff['objects'][0].__class__.__name__,
                                    el_diff['objects'][0].serialize(),
                                    el_diff['objects'][1].__class__.__name__,
                                    el_diff['objects'][1].serialize(),
                                )
                                new_to_render.append(
                                    [el_diff, indent + 3, el_prefix, ])
                            else:
                                new_to_msg += '\n' + ' ' * \
                                    2 * (indent + 2) + el_diff

                        if new_to_msg:
                            msg += prefix + new_to_msg
                            prefix = ''

                        if new_to_render:
                            new_to_render[0][2] = prefix + new_to_render[0][2]
                            new_to_render.reverse()
                            to_render.extend(new_to_render)
                    else:
                        msg += prefix + '\n' + ' ' * 2 * \
                            (indent + 2) + difference['attributes'][attr_name]

        return msg

    def get_primary_attribute(self):
        """ Get value of primary attribute

        Returns:
            :obj:`object`: value of primary attribute
        """
        if self.__class__.Meta.primary_attribute:
            return getattr(self, self.__class__.Meta.primary_attribute.name)

        return None

    def serialize(self):
        """ Get value of primary attribute

        Returns:
            :obj:`str`: value of primary attribute
        """
        return self.get_primary_attribute()

    @classmethod
    def deserialize(cls, value, objects):
        """ Deserialize value

        Args:
            value (:obj:`str`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value
                and cleaning error
        """
        if value in objects.get(cls, {}):
            return (objects[cls][value], None)

        attr = cls.Meta.primary_attribute
        return (None, InvalidAttribute(attr, ['No object with primary attribute value "{}"'.format(value)]))

    @staticmethod
    def get_all_related(objs, forward=True, reverse=True):
        """ Optimally obtain all objects related to objects in `objs`

        The set of all :obj:`Model`\ s can be viewed as a graph whose nodes are :obj:`Model` instances
        and whose edges are related connections. Because related edges are bi-directional, this graph
        is a set of strongly connected components and no edges connect the components.

        The algorithm here finds all :obj:`Model`\ s that are reachable from a set of instances
        in `O(n)`, where `n` is the size of the reachable set. This algorithm is optimal.
        It achieves this performance because `obj.get_related()` takes `O(n(c))` where `n(c)` is the
        number of nodes in the component containing `obj`, and each component is only explored
        once because all of a component's nodes are stored in `found_objs` when the component is first
        explored.

        In addition, this method is deterministic because ordered dictionaries preserve insertion order.

        Args:
            objs (:obj:`iterator` of :obj:`Model`): some objects
            forward (:obj:`bool`, optional): if :obj:`True`, get all forward related objects
            reverse (:obj:`bool`, optional): if :obj:`True`, get all reverse related objects

        Returns:
            :obj:`list` of :obj:`Model`: all objects in `objs` and all objects related to them,
            without any duplicates
        """
        found_objs = collections.OrderedDict()
        for obj in objs:
            if obj not in found_objs:
                found_objs[obj] = None
                for related_obj in obj.get_related(forward=forward, reverse=reverse):
                    if related_obj not in found_objs:
                        found_objs[related_obj] = None
        return list(found_objs)

    def get_related(self, forward=True, reverse=True):
        """ Get all related objects reachable from `self`

        Args:
            forward (:obj:`bool`, optional): if :obj:`True`, get all forward related objects
            reverse (:obj:`bool`, optional): if :obj:`True`, get all reverse related objects

        Returns:
            :obj:`list` of :obj:`Model`: related objects, without any duplicates
        """
        related_objs = collections.OrderedDict()
        objs_to_explore = [self]
        init_iter = True
        while objs_to_explore:
            obj = objs_to_explore.pop()
            if obj not in related_objs:
                if not init_iter:
                    related_objs[obj] = None
                init_iter = False

                cls = obj.__class__
                attrs = []
                if forward:
                    attrs = chain(attrs, cls.Meta.attributes.items())
                if reverse:
                    attrs = chain(attrs, cls.Meta.related_attributes.items())
                for attr_name, attr in attrs:
                    if isinstance(attr, RelatedAttribute):
                        value = getattr(obj, attr_name)

                        if isinstance(value, list):
                            objs_to_explore.extend(value)
                        elif value is not None:
                            objs_to_explore.append(value)

        return list(related_objs)

    def clean(self):
        """ Clean all of this `Model`'s attributes

        Returns:
            :obj:`InvalidObject` or None: `None` if the object is valid,
                otherwise return a list of errors as an instance of `InvalidObject`
        """
        errors = []

        for attr_name, attr in self.Meta.attributes.items():
            value = getattr(self, attr_name)
            clean_value, error = attr.clean(value)

            if error:
                errors.append(error)
            else:
                self.__setattr__(attr_name, clean_value)

        if errors:
            return InvalidObject(self, errors)
        return None

    def validate(self):
        """ Determine if the object is valid

        Returns:
            :obj:`InvalidObject` or None: `None` if the object is valid,
                otherwise return a list of errors as an instance of `InvalidObject`
        """
        errors = []

        # attributes
        for attr_name, attr in self.Meta.attributes.items():
            error = attr.validate(self, getattr(self, attr_name))
            if error:
                errors.append(error)

        # related attributes
        for attr_name, attr in self.Meta.related_attributes.items():
            if attr.related_name:
                error = attr.related_validate(self, getattr(self, attr.related_name))
                if error:
                    errors.append(error)

        if errors:
            return InvalidObject(self, errors)
        return None

    @classmethod
    def validate_unique(cls, objects):
        """ Validate attribute uniqueness

        Args:
            objects (:obj:`list` of :obj:`Model`): list of objects

        Returns:
            :obj:`InvalidModel` or `None`: list of invalid attributes and their errors
        """
        errors = []

        # validate uniqueness of individual attributes
        for attr_name, attr in cls.Meta.attributes.items():
            if attr.unique:
                vals = []
                for obj in objects:
                    vals.append(getattr(obj, attr_name))

                error = attr.validate_unique(objects, vals)
                if error:
                    errors.append(error)

        # validate uniqueness of combinations of attributes
        for unique_together in cls.Meta.unique_together:
            vals = set()
            rep_vals = set()
            for obj in objects:
                val = []
                for attr_name in unique_together:
                    attr_val = getattr(obj, attr_name)
                    if isinstance(attr_val, RelatedManager):
                        val.append(tuple(sorted((sub_val.serialize() for sub_val in attr_val))))
                    elif isinstance(attr_val, Model):
                        val.append(attr_val.serialize())
                    else:
                        val.append(attr_val)
                val = tuple(val)

                if val in vals:
                    rep_vals.add(val)
                else:
                    vals.add(val)

            if rep_vals:
                msg = ("Combinations of ({}) must be unique across all instances of this class. "
                       "The following combinations are repeated:".format(
                           ', '.join(unique_together)))
                for rep_val in rep_vals:
                    msg += '\n  {}'.format(', '.join((str(x)
                                                      for x in rep_val)))
                attr = cls.Meta.attributes[list(unique_together)[0]]
                errors.append(InvalidAttribute(attr, [msg]))

        # return
        if errors:
            return InvalidModel(cls, errors)
        return None

    DEFAULT_MAX_DEPTH = 2
    DEFAULT_INDENT = 3

    def pprint(self, stream=None, max_depth=DEFAULT_MAX_DEPTH, indent=DEFAULT_INDENT):
        if stream is None:
            stream = sys.stdout
        print(self.pformat(max_depth=max_depth, indent=indent), file=stream)

    def pformat(self, max_depth=DEFAULT_MAX_DEPTH, indent=DEFAULT_INDENT):
        """ Return a human-readable string representation of this `Model`.

            Follows the graph of related `Model`'s up to a depth of `max_depth`. `Model`'s at depth
            `max_depth+1` are represented by '<class name>: ...', while deeper `Model`'s are not
            traversed or printed. Re-encountered Model's do not get printed, and are indicated by
            '<attribute name>: --'.
            Attributes that are related or iterable are indented.

            For example, we have::

                Model1_classname:       # Each model starts with its classname, followed by a list of
                    attr1: value1           # attribute names & values.
                    attr2: value2
                    attr3:                  # Reference attributes can point to other Models; we indent these under the attribute name
                        Model2_classname:   # Reference attribute attr3 contains Model2;
                            ...                 # its attributes follow.
                    attr4:
                        Model3_classname:   # An iteration over reference attributes is a list at constant indentation:
                            ...
                    attr5:
                        Model2_classname: --    # Traversing the Model network may re-encounter a Model; they're listed with '--'
                    attr6:
                        Model5_classname:
                            attr7:
                                Model5_classname: ...   # The size of the output is controlled with max_depth;
                                                        # models encountered at depth = max_depth+1 are shown with '...'

        Args:
            max_depth (:obj:`int`, optional): the maximum depth to which related `Model`'s should be printed
            indent (:obj:`int`, optional): number of spaces to indent

        Returns:
            :obj:str: readable string representation of this `Model`
        """
        printed_objs = set()
        return indent_forest(self._tree_str(printed_objs, depth=0, max_depth=max_depth), indentation=indent)

    def _tree_str(self, printed_objs, depth, max_depth):
        """ Obtain a nested list of string representations of this Model.

            Follows the graph of related `Model`'s up to a depth of `max_depth`. Called recursively.

        Args:
            printed_objs (:obj:`set`): objects that have already been `_tree_str`'ed
            depth (:obj:`int`): the depth at which this `Model` is being `_tree_str`'ed
            max_depth (:obj:`int`): the maximum depth to which related `Model`'s should be printed

        Returns:
            :obj:`list` of :obj:`list`: a nested list of string representations of this Model

        Raises:
            :obj:`ValueError`: if an attribute cannot be represented as a string, or a
            related attribute value is not `None`, a `Model`, or an Iterable
        """
        '''
        TODO: many possible improvements
            output to formattable text, most likely html
                in html, distinguish class names, attribute names, and values; link to previously
                printed Models; make deeper references collapsable
            could convert to YAML, and use YAML renderers
            take iterable of models instead of one
            take sets of attributes to print, or not print
            don't display empty attributes
        '''
        # get class
        cls = self.__class__

        # check depth
        if max_depth < depth:
            return ["{}: {}".format(cls.__name__, '...')]

        printed_objs.add(self)

        # get attribute names and their string values
        attrs = []

        # first do the attributes in cls.Meta.attribute_order in that order,
        # then do the rest
        all_attrs = cls.Meta.attributes.copy()
        all_attrs.update(cls.Meta.related_attributes)
        ordered_attrs = []
        flat_attr_order = cls.Meta.attribute_order
        for name in flat_attr_order:
            ordered_attrs.append((name, all_attrs[name]))
        for name in all_attrs.keys():
            if name not in flat_attr_order:
                ordered_attrs.append((name, all_attrs[name]))
        for name, attr in ordered_attrs:
            val = getattr(self, name)

            if isinstance(attr, RelatedAttribute):
                if val is None:
                    attrs.append((name, val))
                elif isinstance(val, Model):
                    if val in printed_objs:
                        attrs.append((name, '--'))
                    else:
                        attrs.append((name, ''))
                        attrs.append(val._tree_str(
                            printed_objs, depth + 1, max_depth))
                elif isinstance(val, (set, list, tuple)):
                    attrs.append((name, ''))
                    iter_attr = []
                    for v in val:
                        if v not in printed_objs:
                            iter_attr.append(v._tree_str(
                                printed_objs, depth + 1, max_depth))
                    attrs.extend(iter_attr)
                else:
                    raise ValueError("Related attribute '{}' has invalid value".format(
                        name))  # pragma: no cover # unreachable due to other error checking

            elif isinstance(attr, Attribute):
                if val is None:
                    attrs.append((name, val))
                elif isinstance(val, (str, bool, int, float, Enum)):
                    attrs.append((name, str(val)))
                elif hasattr(attr, 'serialize'):
                    attrs.append((name, attr.serialize(val)))
                else:
                    raise ValueError("Attribute '{}' has invalid value '{}'".format(
                        name, str(val)))  # pragma: no cover # unreachable due to other error checking

            else:
                raise ValueError("Attribute '{}' is not an Attribute or RelatedAttribute".format(name)
                                 )  # pragma: no cover # unreachable due to other error checking

        rv = ["{}:".format(cls.__name__)]
        nested = []
        for item in attrs:
            if isinstance(item, tuple):
                name, val = item
                if val == '':
                    nested.append("{}:".format(name))
                else:
                    nested.append("{}: {}".format(name, val))
            else:
                nested.append(item)
        rv.append(nested)
        return rv

    def copy(self):
        """ Create a copy

        Returns:
            :obj:`Model`: model copy
        """

        # initialize copies of objects
        objects_and_copies = {}
        for obj in chain([self], self.get_related()):
            copy = obj.__class__()
            objects_and_copies[obj] = copy

        # copy attribute values
        for obj, copy in objects_and_copies.items():
            obj._copy_attributes(copy, objects_and_copies)

        # copy expressions
        for o in objects_and_copies.values():
            is_expression = next((True for cls in get_superclasses(o.__class__)
                                  if cls.__module__ == 'obj_tables.math.expression'
                                  and cls.__name__ == 'Expression'), False)
            if is_expression:
                objs = {o.__class__: {o.serialize(): o}}
                for attr_name, attr in o.Meta.attributes.items():
                    if isinstance(attr, RelatedAttribute) and \
                            attr.related_class.__name__ in o.Meta.expression_term_models:
                        objs[attr.related_class] = {}
                        for oo in getattr(o, attr_name):
                            objs[attr.related_class][oo.serialize()] = oo

                ((attr_name, attr),) = o.Meta.related_attributes.items()
                expr, error = o.deserialize(o.expression, objs)
                assert error is None, str(error)
                setattr(getattr(o, attr_name), attr.name, expr)

        # return copy
        return objects_and_copies[self]

    def _copy_attributes(self, other, objects_and_copies):
        """ Copy the attributes from `self` to its new copy, `other`

        Args:
            other (:obj:`Model`): object to copy attribute values to
            objects_and_copies (:obj:`dict` of `Model`: `Model`): dictionary of pairs of objects and their new copies

        Raises:
            :obj:`ValueError`: if related attribute value is not `None`, a `Model`, or an Iterable,
                or if a non-related attribute is not an immutable
        """
        # get class
        cls = self.__class__

        # copy attributes
        for attr in cls.Meta.attributes.values():
            val = getattr(self, attr.name)
            copy_val = attr.copy_value(val, objects_and_copies)
            setattr(other, attr.name, copy_val)

    @classmethod
    def is_serializable(cls):
        """ Determine if the class (and its related classes) can be serialized

        Raises:
            :obj:`bool`: `True` if the class can be serialized
        """
        classes_to_check = [cls]
        checked_classes = []
        while classes_to_check:
            cls = classes_to_check.pop()
            if cls not in checked_classes:
                checked_classes.append(cls)

                if not isinstance(cls, type):
                    raise ValueError("Related class '{}' must be a `Model`".format(cls))

                if not issubclass(cls, Model):
                    raise ValueError("Related class '{}' must be a `Model`".format(
                        cls.__name__))

                if not cls.are_related_attributes_serializable():
                    return False

                for attr in cls.Meta.attributes.values():
                    if isinstance(attr, RelatedAttribute):
                        classes_to_check.append(attr.related_class)

                for attr in cls.Meta.related_attributes.values():
                    if isinstance(attr, RelatedAttribute):
                        classes_to_check.append(attr.primary_class)

        return True

    @classmethod
    def are_related_attributes_serializable(cls):
        """ Determine if the immediate related attributes of the class can be serialized

        Returns:
            :obj:`bool`: `True` if the related attributes can be serialized
        """
        for attr in cls.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute):

                # setup related attributes on related classes
                if attr.name in cls.__dict__ and attr.related_name and \
                        isinstance(attr.related_class, type) and issubclass(attr.related_class, Model):
                    related_classes = chain(
                        [attr.related_class], get_subclasses(attr.related_class))
                    for related_class in related_classes:
                        # check that related class has primary attributes
                        if isinstance(attr, (
                            OneToOneAttribute,
                            OneToManyAttribute,
                            ManyToOneAttribute,
                            ManyToManyAttribute)) and \
                                attr.__class__ not in (
                                    OneToOneAttribute,
                                    OneToManyAttribute,
                                    ManyToOneAttribute,
                                    ManyToManyAttribute) and \
                                'serialize' in attr.__class__.__dict__ and \
                                'deserialize' in attr.__class__.__dict__:
                            pass
                        elif isinstance(attr, (OneToOneAttribute, ManyToOneAttribute)) and \
                            attr.related_class.Meta.table_format == TableFormat.multiple_cells and \
                                'serialize' in attr.related_class.__dict__:
                            pass
                        elif not related_class.Meta.primary_attribute:
                            if related_class.Meta.table_format == TableFormat.cell:
                                warnings.warn('Primary class: {}: Related class {} must have a primary attribute'.format(
                                    attr.primary_class.__name__, related_class.__name__), SchemaWarning)
                            else:
                                return False
                        elif not related_class.Meta.primary_attribute.unique and not related_class.Meta.unique_together:
                            if related_class.Meta.table_format == TableFormat.cell:
                                warnings.warn('Primary attribute {} of related class {} must be unique'.format(
                                    related_class.Meta.primary_attribute.name, related_class.__name__), SchemaWarning)
                            else:
                                return False
        return True

    @classmethod
    def get_manager(cls):
        """ Get the manager for the model

        Return:
            :obj:`Manager`: manager
        """
        return cls.objects

    def __enter__(self):
        """ Enter context """
        return self

    def __exit__(self, type, value, traceback):
        """ Exit context """
        pass

    @staticmethod
    def to_dict(object, models=None, encode_primary_objects=True, encoded=None):
        """ Encode a instance of :obj:`Model` or a collection of instances of :obj:`Model` using a simple Python representation
        (dict, list, str, float, bool, None) that is compatible with JSON and YAML. Use `__id` keys to avoid infinite recursion
        by encoding each object once and referring to objects by their __id for each repeated reference.

        Args:
            object (:obj:`object`): instance of :obj:`Model` or a collection (:obj:`dict`, :obj:`list`, :obj:`tuple`, or nested
                combination of :obj:`dict`, :obj:`list`, and :obj:`tuple`) of instances of :obj:`Model`
            models (:obj:`str`, optional): list of models to encode into JSON
            encode_primary_objects (:obj:`bool`, optional): if :obj:`True`, encode primary classes otherwise just encode their IDs
            encoded (:obj:`dict`, optional): objects that have already been encoded and their assigned JSON identifiers

        Returns:
            :obj:`dict`: simple Python representation of the object
        """
        if models is None:
            models = set()

        if encoded is None:
            encoded = {}

        to_encode = queue.Queue()

        def add_to_encoding_queue(object, encoded=encoded, to_encode=to_encode):
            if isinstance(object, Model):
                cls = object.__class__
                encoded_json = encoded.get(object, None)
                if encoded_json:
                    json = {
                        '__id': encoded_json['__id'],
                    }
                else:
                    json = {
                        '__id': len(encoded),
                    }
                    encoded[object] = json
                    to_encode.put((object, json))
                json['__type'] = cls.__name__
                if cls.Meta.primary_attribute:
                    json[cls.Meta.primary_attribute.name] = object.get_primary_attribute()
            elif isinstance(object, (list, tuple)):
                json = []
                to_encode.put((object, json))
            elif isinstance(object, (dict, collections.OrderedDict)):
                json = {}
                to_encode.put((object, json))
            elif isinstance(object, (type(None), str, bool, int, float)):
                json = object
            else:
                raise ValueError('Instance of {} cannot be encoded'.format(object.__class__.__name__))
            return json

        # encode objects into JSON
        return_val = add_to_encoding_queue(object)

        while not to_encode.empty():
            obj, json_obj = to_encode.get()

            if isinstance(obj, Model):
                cls = obj.__class__
                models.add(cls)

                if encode_primary_objects or cls.Meta.table_format == TableFormat.cell:
                    for attr_name, attr in chain(cls.Meta.attributes.items(), cls.Meta.related_attributes.items()):
                        val = getattr(obj, attr_name)
                        if isinstance(attr, RelatedAttribute):
                            if val is None:
                                json_val = None
                            elif isinstance(val, list):
                                json_val = []
                                for v in val:
                                    json_val.append(add_to_encoding_queue(v))
                            else:
                                json_val = add_to_encoding_queue(val)
                        else:
                            json_val = attr.to_builtin(val)
                        json_obj[attr_name] = json_val

            elif isinstance(obj, (list, tuple)):
                for sub_obj in obj:
                    json_obj.append(add_to_encoding_queue(sub_obj))

            elif isinstance(obj, dict):
                for key, val in obj.items():
                    json_obj[add_to_encoding_queue(key)] = add_to_encoding_queue(val)

            else:  # pragma no cover
                # unreachable because only instances of Model, list, tuple, and dict can be added to the encoding queue
                pass

        # check that it will be possible to decode the data out of JSON
        if len(models) > len(set([model.__name__ for model in models])):
            raise ValueError('Model names must be unique to encode objects')

        # return JSON-encoded data
        return return_val

    @staticmethod
    def from_dict(json, models, decode_primary_objects=True, primary_objects=None, decoded=None, ignore_extra_models=False,
                  validate=False, output_format=None):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of an object that
        is compatible with JSON and YAML, including references to objects through `__id` keys.

        Args:
            json (:obj:`dict`): simple Python representation of the object
            decode_primary_objects (:obj:`bool`, optional): if :obj:`True`, decode primary classes otherwise
                just look up objects by their IDs
            primary_objects (:obj:`list`, optional): list of instances of primary classes (i.e. non-line classes)
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded
            ignore_extra_models (:obj:`bool`, optional): if :obj:`True` and all `models` are found, ignore
                other worksheets or files
            validate (:obj:`bool`, optional): if :obj:`True`, validate the data
            output_format (:obj:`str`, optional): desired structure of the return value

                * `None`: Return the data with the same structure as :obj:`json`. Do not reshape the data.
                * `list`: List of instances of :obj:`Model`.
                * `dict`: Dictionary that maps subclasses of :obj:`Model` to the instances of each subclass.

        Returns:
            :obj:`Model`: decoded object
        """
        models = set(models)
        for model in list(models):
            models.update(set(get_related_models(model)))
        models_by_name = {model.__name__: model for model in models}
        if len(list(models_by_name.keys())) < len(models):
            raise ValueError('Model names must be unique to decode objects')

        if primary_objects is None:
            primary_objects = []

        if decoded is None:
            decoded = {}
        to_decode = []

        def add_to_decoding_queue(json, models_by_name=models_by_name, decoded=decoded, to_decode=to_decode,
                                  ignore_extra_models=ignore_extra_models):
            if isinstance(json, dict) and '__type' in json and (not ignore_extra_models or (json['__type'] in models_by_name)):
                obj_type = json.get('__type')
                model = models_by_name.get(obj_type, None)
                if not model:
                    raise ValueError('Unsupported type {}'.format(obj_type))
                else:
                    obj = decoded.get(json['__id'], None)
                    if obj is None:
                        obj = model()
                        decoded[json['__id']] = obj
                    to_decode.append((json, obj))
            elif isinstance(json, list):
                obj = []
                to_decode.append((json, obj))
            elif isinstance(json, dict):
                obj = {}
                to_decode.append((json, obj))
            else:
                obj = json

            return obj

        return_val = add_to_decoding_queue(json)

        while to_decode:
            obj_json, obj = to_decode.pop()
            if isinstance(obj, Model):
                cls = obj.__class__

                for attr_name, attr in chain(cls.Meta.attributes.items(), cls.Meta.related_attributes.items()):
                    if attr_name not in obj_json:
                        continue

                    attr_json = obj_json[attr_name]
                    if isinstance(attr, RelatedAttribute):
                        if attr_name in cls.Meta.attributes:
                            other_cls = attr.related_class
                        else:
                            other_cls = attr.primary_class

                        if attr_json is None:
                            attr_val = None

                        elif isinstance(attr_json, list):
                            attr_val = []
                            for sub_attr_json in attr_json:
                                if decode_primary_objects or other_cls.Meta.table_format == TableFormat.cell:
                                    sub_obj = add_to_decoding_queue(sub_attr_json)
                                else:
                                    primary_attr = sub_attr_json[other_cls.Meta.primary_attribute.name]
                                    sub_obj = primary_objects[other_cls][primary_attr]
                                attr_val.append(sub_obj)

                        else:
                            if decode_primary_objects or other_cls.Meta.table_format == TableFormat.cell:
                                attr_val = add_to_decoding_queue(attr_json)
                            else:
                                primary_attr = attr_json[other_cls.Meta.primary_attribute.name]
                                attr_val = primary_objects[other_cls][primary_attr]

                    else:
                        attr_val = attr.from_builtin(attr_json)
                    setattr(obj, attr_name, attr_val)

            elif isinstance(obj, list):
                for sub_json in obj_json:
                    obj.append(add_to_decoding_queue(sub_json))

            elif isinstance(obj, dict):
                for key, val in obj_json.items():
                    obj[add_to_decoding_queue(key)] = add_to_decoding_queue(val)

            else:  # pragma no cover
                # unreachable because only instances of Model, list, tuple, and dict can be added to the encoding queue
                pass

        # validate
        if validate:
            errors = Validator().validate(decoded.values())
            if errors:
                raise ValueError(
                    indent_forest(['The data cannot be loaded because it fails to validate:', [errors]]))

        # format output
        if output_format == 'list':
            return_val = list(decoded.values())
        elif output_format == 'dict':
            return_val = {}
            for obj in decoded.values():
                if obj.__class__ not in return_val:
                    return_val[obj.__class__] = []
                return_val[obj.__class__].append(obj)
        elif output_format is not None:
            raise ValueError('Output format must be `None`, `list`, or `dict`')

        # return data
        return return_val

    def has_attr_vals(self, __type=None, __check_attr_defined=True, **kwargs):
        """ Check if the type and values of the attributes of an object match a set of conditions

        Args:
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            __check_attr_defined (:obj:`bool`, optional): if :obj:`True`, raise an exception if the queried
                attribute is not defined
            **kwargs: dictionary of attribute name/value pairs to find matching
                object or create new object

        Returns:
            :obj:`bool`: :obj:`True` if the object is an instance of :obj:`__type` and the
                the values of the attributes of the object match :obj:`kwargs`
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')
        if '__check_attr_defined' in kwargs:
            __check_attr_defined = kwargs.pop('__check_attr_defined')

        if __type and not isinstance(self, __type):
            return False

        for attr, val in kwargs.items():
            if __check_attr_defined and attr not in self.Meta.local_attributes:
                raise AttributeError("'{}' object has no attribute '{}'".format(self.__class__.__name__, attr))

            if not hasattr(self, attr) or getattr(self, attr) != val:
                return False

        return True

    def get_children(self, kind=None, __type=None, recursive=True, **kwargs):
        """ Get a kind of children.

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to get
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            recursive (:obj:`bool`, optional): if :obj:`True`, get children recursively
            **kwargs: dictionary of attribute name/value pairs

        Returns:
            :obj:`list` of :obj:`Model`: children
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        children = self.get_immediate_children(kind=kind)

        # get recursive children
        if recursive:
            objs_to_explore = children
            children = set(children)
            while objs_to_explore:
                obj_to_explore = objs_to_explore.pop()
                for child in obj_to_explore.get_immediate_children(kind=kind):
                    if child not in children:
                        children.add(child)
                        objs_to_explore.append(child)
            children = list(children)

        # filter by type/attributes
        matches = []
        for child in children:
            if child.has_attr_vals(__type=__type, __check_attr_defined=False, **kwargs):
                matches.append(child)
        children = matches

        # return children
        return children

    def get_immediate_children(self, kind=None, __type=None, **kwargs):
        """ Get a kind of immediate children

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to get
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            **kwargs: dictionary of attribute name/value pairs

        Returns:
            :obj:`list` of :obj:`Model`: immediate children
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        if kind is None:
            attr_names = [attr.name for attr in self.Meta.attributes.values() if isinstance(attr, RelatedAttribute)]
        elif kind == '__all__':
            attr_names = [attr.name for attr in self.Meta.local_attributes.values() if attr.is_related]
        else:
            attr_names = self.Meta.children.get(kind, ())

        children = []
        for attr_name in attr_names:
            if not isinstance(self.Meta.local_attributes[attr_name].attr, RelatedAttribute):
                raise ValueError('Children are defined via related attributes. "{}" is not a related attribute of "{}.'.format(
                    attr_name, self.__class__.__name__))

            attr_value = getattr(self, attr_name)
            if isinstance(attr_value, list):
                children.extend(attr_value)
            elif attr_value:
                children.append(attr_value)
        children = det_dedupe(children)

        # filter by type/attributes
        matches = []
        for child in children:
            if child.has_attr_vals(__type=__type, __check_attr_defined=False, **kwargs):
                matches.append(child)
        children = matches

        return children

    def cut(self, kind=None):
        """ Cut the object and its children from the rest of the object graph.

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to get

        Returns:
            :obj:`Model`: same object, but cut from the rest of the object graph
        """
        objs = set(self.get_children(kind=kind))
        objs.add(self)

        for obj in objs:
            obj.cut_relations(objs)

        return self

    def cut_relations(self, objs):
        """ Cut relations to objects not in :obj:`objs`.

        Args:
            objs (:obj:`set` of :obj:`Model`): objects to retain relations to
        """
        # iterate over related attributes
        for attr in self.Meta.local_attributes.values():
            if attr.is_related:
                # get value
                val = getattr(self, attr.name)

                # cut relationships to objects not in `objs`
                if isinstance(val, list):
                    # *ToManyAttribute
                    for v in list(val):
                        if v not in objs:
                            val.remove(v)
                else:
                    # *ToOneAttribute
                    if val and val not in objs:
                        setattr(self, attr.name, None)

    def merge(self, other, normalize=True, validate=True):
        """ Merge another model into a model

        Args:
            other (:obj:`Model`): other model
            normalize (:obj:`bool`, optional): if :obj:`True`, normalize models and merged model
            validate (:obj:`bool`, optional): if :obj:`True`, validate models and merged model
        """
        # validate models
        if validate:
            error = Validator().run(self, get_related=True)
            assert error is None, str(error)

            error = Validator().run(other, get_related=True)
            assert error is None, str(error)

        # normalize models so merging is reproducible
        if normalize:
            self.normalize()
            other.normalize()

        # generate mapping from self to other
        other_objs_in_self, other_objs_not_in_self = self.gen_merge_map(other)
        self_objs_in_other, self_objs_not_in_other = other.gen_merge_map(self)

        # merge object graph
        for other_child, self_child in other_objs_in_self.items():
            if self_child != self:
                self_child.merge_attrs(other_child, other_objs_in_self, self_objs_in_other)
        for other_child in other_objs_not_in_self:
            other_child.merge_attrs(other_child, other_objs_in_self, self_objs_in_other)

        # merge attributes
        self.merge_attrs(other, other_objs_in_self, self_objs_in_other)

        # normalize so left merge and right merge produce same results
        if normalize:
            self.normalize()

        # validate model
        if validate:
            error = Validator().run(self, get_related=True)
            assert error is None, str(error)

    def gen_merge_map(self, other):
        """ Create a dictionary that maps instances of objects in another model to objects
        in a model

        Args:
            other (:obj:`Model`): other model

        Returns:
            :obj:`dict`: dictionary that maps instances of objects in another model to objects
                in a model
            :obj:`list`: list of instances of objects in another model which have no parallel
                in the model
        """
        self_objs_by_class = self.gen_serialized_val_obj_map()
        other_objs_by_class = other.gen_serialized_val_obj_map()

        other_objs_in_self = {}
        other_objs_not_in_self = []
        for type, other_type_objs in other_objs_by_class.items():
            for serialized_val, other_obj in other_type_objs.items():
                self_obj = self_objs_by_class.get(type, {}).get(serialized_val, None)
                if self_obj:
                    other_objs_in_self[other_obj] = self_obj
                else:
                    other_objs_not_in_self.append(other_obj)

        # force mapping for other --> self
        if other in other_objs_in_self:
            if other_objs_in_self[other] != self:
                raise ValueError('Other must map to self')
        else:
            other_objs_in_self[other] = self
            other_objs_not_in_self.remove(other)

        return (other_objs_in_self, other_objs_not_in_self)

    def gen_serialized_val_obj_map(self):
        """ Generate mappings from serialized values to objects

        Returns:
            :obj:`dict`: dictionary which maps types of models to dictionaries which serialized values to objects

        Raises:
            :obj:`ValueError`: if serialized values are not unique within each type
        """
        objs = self.get_related()
        objs_by_class = {}
        for obj in objs:
            if obj.__class__ not in objs_by_class:
                objs_by_class[obj.__class__] = {}
            serialized_val = obj.serialize()
            if serialized_val in objs_by_class[obj.__class__]:
                raise ValueError('Serialized value "{}" is not unique for {}'.format(serialized_val, obj.__class__.__name__))
            objs_by_class[obj.__class__][serialized_val] = obj
        return objs_by_class

    def merge_attrs(self, other, other_objs_in_self, self_objs_in_other):
        """ Merge attributes of two objects

        Args:
            other (:obj:`Model`): other model
            other_objs_in_self (:obj:`dict`): dictionary that maps instances of objects in another model to objects
                in a model
            self_objs_in_other (:obj:`dict`): dictionary that maps instances of objects in a model to objects
                in another model
        """
        if self.Meta.merge == ModelMerge.append and self != other:
            raise ValueError('{} cannot be joined'.format(self.Meta.verbose_name_plural))

        for attr in self.Meta.attributes.values():
            attr.merge(self, other, other_objs_in_self, self_objs_in_other)


class ModelSource(object):
    """ Represents the file, sheet, columns, and row where a :obj:`Model` instance was defined

    Attributes:
        path_name (:obj:`str`): pathname of source file for object
        sheet_name (:obj:`str`): name of spreadsheet containing source data for object
        attribute_seq (:obj:`list`): sequence of attribute names in source file; blank values
            indicate attributes that were ignored
        row (:obj:`int`): row number of object in its source file
        table_id (:obj:`str`): id of the source table
    """

    def __init__(self, path_name, sheet_name, attribute_seq, row, table_id=None):
        """
        Args:
            path_name (:obj:`str`): pathname of source file for object
            sheet_name (:obj:`str`): name of spreadsheet containing source data for object
            attribute_seq (:obj:`list`): sequence of attribute names in source file; blank values
                indicate attributes that were ignored
            row (:obj:`int`): row number of object in its source file
            table_id (:obj:`str`, optional): id of the source table
        """
        self.path_name = path_name
        self.sheet_name = sheet_name
        self.attribute_seq = attribute_seq
        self.row = row
        self.table_id = table_id


class Attribute(object, metaclass=abc.ABCMeta):
    """ Model attribute

    Attributes:
        name (:obj:`str`): name
        type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): allowed type(s) of the values of the attribute
        init_value (:obj:`object`): initial value
        default (:obj:`object`): default value
        default_cleaned_value (:obj:`object`): value to replace
            :obj:`None` values with during cleaning, or function
            which computes the value to replace :obj:`None` values
        none_value (:obj:`object`): none value
        verbose_name (:obj:`str`): verbose name
        description (:obj:`str`): description
        primary (:obj:`bool`): indicate if attribute is primary attribute
        unique (:obj:`bool`): indicate if attribute value must be unique
        unique_case_insensitive (:obj:`bool`): if true, conduct case-insensitive test of uniqueness
    """

    def __init__(self, init_value=None, default=None, default_cleaned_value=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            init_value (:obj:`object`, optional): initial value
            default (:obj:`object`, optional): default value
            default_cleaned_value (:obj:`object`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """
        self.name = None
        self.type = object
        self.init_value = init_value
        self.default = default
        self.default_cleaned_value = default_cleaned_value
        self.none_value = none_value
        self.verbose_name = verbose_name
        self.description = description
        self.primary = primary
        self.unique = unique
        self.unique_case_insensitive = unique_case_insensitive

    def get_init_value(self, obj):
        """ Get initial value for attribute

        Args:
            obj (:obj:`Model`): object whose attribute is being initialized

        Returns:
            :obj:`object`: initial value
        """
        return copy.copy(self.init_value)

    def get_default(self):
        """ Get default value for attribute

        Returns:
            :obj:`object`: initial value
        """
        if callable(self.default):
            return self.default()

        return copy.deepcopy(self.default)

    def get_default_cleaned_value(self):
        """ Get value to replace :obj:`None` values with during cleaning

        Returns:
            :obj:`object`: initial value
        """
        if callable(self.default_cleaned_value):
            return self.default_cleaned_value()

        return copy.deepcopy(self.default_cleaned_value)

    def get_none_value(self):
        """ Get none value

        Returns:
            :obj:`object`: none value
        """
        if callable(self.none_value):
            return self.none_value()

        return copy.deepcopy(self.none_value)

    def set_value(self, obj, new_value):
        """ Set value of attribute of object

        Args:
            obj (:obj:`Model`): object
            new_value (:obj:`object`): new attribute value

        Returns:
            :obj:`object`: attribute value
        """
        return new_value

    def value_equal(self, val1, val2, tol=0.):
        """ Determine if attribute values are equal

        Args:
            val1 (:obj:`object`): first value
            val2 (:obj:`object`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        return val1 == val2

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        return (value, None)

    @abc.abstractmethod
    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, otherwise return a list
                of errors as an instance of `InvalidAttribute`
        """
        pass  # pragma: no cover

    def validate_unique(self, objects, values):
        """ Determine if the attribute values are unique

        Args:
            objects (:obj:`list` of :obj:`Model`): list of `Model` objects
            values (:obj:`list`): list of values

        Returns:
           :obj:`InvalidAttribute` or None: None if values are unique, otherwise return a list of
            errors as an instance of `InvalidAttribute`
        """
        unq_vals = set()
        rep_vals = set()

        for val in values:
            if self.unique_case_insensitive and isinstance(val, str):
                val = val.lower()
            if val in unq_vals:
                rep_vals.add(val)
            else:
                unq_vals.add(val)

        if rep_vals:
            message = "{} values must be unique, but these values are repeated: {}".format(
                self.name, ', '.join([quote(val) for val in rep_vals]))
            return InvalidAttribute(self, [message])

    @abc.abstractmethod
    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`object`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`object`: copy of value
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def serialize(self, value):
        """ Serialize value

        Args:
            value (:obj:`object`): Python representation

        Returns:
            :obj:`bool`, `float`, `str`, or `None`: simple Python representation
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`object`): semantically equivalent representation

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`object`): value of the attribute

        Returns:
            :obj:`object`: simple Python representation of a value of the attribute
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`object`): simple Python representation of a value of the attribute

        Returns:
            :obj:`object`: decoded value of the attribute
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model
        """
        pass  # pragma: no cover

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        return wc_utils.workbook.io.FieldValidation(
            input_title=self.verbose_name,
            input_message=self.description,
            error_title=self.verbose_name,
            error_message=self.description)

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        return self.__class__.__name__.rpartition('Attribute')[0]


class LocalAttribute(object):
    """ Meta data about a local attribute in a class

    Attributes:
        attr (:obj:`Attribute`): attribute
        cls (:obj:`type`): class which owns this attribute
        name (:obj:`str`): name of the :obj:`attr` in :obj:`cls`
        type (:obj:`types.TypeType`): allowed type(s) of the values of the attribute
        related_class (:obj:`type`): other class which is related to this attribute
        related_name (:obj:`str`): name of this attribute in :obj:`related_cls`
        primary_class (:obj:`type`): class in which this attribute was defined
        primary_name (:obj:`str`): name of this attribute in :obj:`primary_cls`
        secondary_class (:obj:`type`): related class to :obj:`primary_cls`
        secondary_name (:obj:`str`): name of this attribute in :obj:`secondary_cls`
        is_primary (:obj:`bool`): :obj:`True` if this :obj:`attr` was defined in :obj:`cls` (:obj:`cls`\ =\ :obj:`primary_cls`)
        is_related (:obj:`bool`): :obj:`True` if this attribute is an instance of :obj:`RelatedAttribute`
        is_related_to_many (:obj:`bool`): :obj:`True` if the value of this attribute is a list (\*-to-many relationship)
        min_related (:obj:`int`): minimum number of related objects in the forward direction
        max_related (:obj:`int`): maximum number of related objects in the forward direction
        min_related_rev (:obj:`int`): minimum number of related objects in the reverse direction
        max_related_rev (:obj:`int`): maximum number of related objects in the reverse direction
    """

    def __init__(self, attr, primary_class, is_primary=True):
        """
        Args:
            attr (:obj:`Attribute`): attribute
            primary_class (:obj:`type`): class in which :obj:`attr` was defined
            is_primary (:obj:`bool`, optional): :obj:`True` indicates that a local attribute should be created
                for the related class of :obj:`attr`
        """
        self.attr = attr
        self.primary_name = attr.name
        if isinstance(attr, RelatedAttribute):
            self.primary_class = attr.primary_class
            self.is_related = True
            self.secondary_class = attr.related_class
            self.secondary_name = attr.related_name
        else:
            self.primary_class = primary_class
            self.is_related = False
            self.secondary_class = None
            self.secondary_name = None

        if is_primary:
            self.cls = primary_class
            self.name = attr.name
            self.type = attr.type
            if isinstance(attr, RelatedAttribute):
                self.related_type = attr.related_type
                self.related_class = attr.related_class
                self.related_name = attr.related_name
                self.min_related = attr.min_related
                self.max_related = attr.max_related
                self.min_related_rev = attr.min_related_rev
                self.max_related_rev = attr.max_related_rev
            else:
                self.related_type = None
                self.related_class = None
                self.related_name = None
                self.min_related = None
                self.max_related = None
                self.min_related_rev = None
                self.max_related_rev = None
            self.is_related_to_many = isinstance(attr, (OneToManyAttribute, ManyToManyAttribute))
        else:
            self.cls = attr.related_class
            self.name = attr.related_name
            self.type = attr.related_type
            self.related_type = attr.type
            self.related_class = attr.primary_class
            self.related_name = attr.name
            self.is_related_to_many = isinstance(attr, (ManyToOneAttribute, ManyToManyAttribute))
            self.min_related = attr.min_related_rev
            self.max_related = attr.max_related_rev
            self.min_related_rev = attr.min_related
            self.max_related_rev = attr.max_related
        self.is_primary = is_primary


class LiteralAttribute(Attribute):
    """ Base class for literal attributes (Boolean, enumeration, float,
    integer, string, etc.)
    """

    def validate(self, obj, value):
        """ Determine if :obj:`value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or :obj:`None`: None if attribute is valid, otherwise return a
                list of errors as an instance of :obj:`InvalidAttribute`
        """
        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`object`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`object`: copy of value
        """
        if value is None:
            return None
        elif isinstance(value, (str, bool, int, float, Enum, )):
            return value
        else:
            return copy.deepcopy(value)

    def serialize(self, value):
        """ Serialize value

        Args:
            value (:obj:`object`): Python representation

        Returns:
            :obj:`bool`, :obj:`float`, :obj:`str`, or :obj:`None`: simple Python
                representation
        """
        return value

    def deserialize(self, value):
        """ Deserialize value

        Args:
            value (:obj:`object`): semantically equivalent representation

        Returns:
            :obj:`tuple` of :obj:`object`, :obj:`InvalidAttribute` or :obj:`None`: tuple
                of cleaned value and cleaning error
        """
        return self.clean(value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation
        (:obj:`dict`, :obj:`list`, :obj:`str`, :obj:`float`, :obj:`bool`, :obj:`None`)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`object`): value of the attribute

        Returns:
            :obj:`object`: simple Python representation of a value of the attribute
        """
        return value

    def from_builtin(self, json):
        """ Decode a simple Python representation (:obj:`dict`, :obj:`list`, :obj:`str`,
        :obj:`float`, :obj:`bool`, :obj:`None`) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`object`): simple Python representation of a value of the attribute

        Returns:
            :obj:`object`: decoded value of the attribute
        """
        return json

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        left_val = getattr(left, self.name)
        right_val = getattr(right, self.name)
        if not self.value_equal(left_val, right_val):
            raise ValueError('{}.{} must be equal'.format(left.__class__.__name__, self.name))


class NumericAttribute(LiteralAttribute):
    """ Base class for numeric literal attributes (float, integer) """
    pass


class EnumAttribute(LiteralAttribute):
    """ Enumeration attribute

    Attributes:
        enum_class (:obj:`type`): subclass of :obj:`Enum`
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, enum_class, none=False, default=None, default_cleaned_value=None, none_value=None, verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            enum_class (:obj:`type` or :obj:`list`): subclass of :obj:`Enum`, :obj:`list` of enumerated names,
                :obj:`list` of 2-tuples of each enumerated name and its value, or a :obj:`dict` which maps
                enumerated names to their values
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`object`, optional): default value
            default_cleaned_value (:obj:`Enum`, optional): value to replace
                :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness

        Raises:
            :obj:`ValueError`: if :obj:`enum_class` is not a subclass of :obj:`Enum`, if :obj:`default` is not an instance
                of :obj:`enum_class`, or if :obj:`default_cleaned_value` is not an instance of :obj:`enum_class`
        """
        if not isinstance(enum_class, type) or not issubclass(enum_class, Enum):
            enum_class = Enum('AttributeEnum', names=enum_class)
        if default is not None:
            if not isinstance(default, enum_class):
                if default in enum_class.__members__:
                    default = enum_class[default]
                else:
                    raise ValueError(
                        '`default` must be `None` or an instance of `enum_class`')
        if default_cleaned_value is not None:
            if not isinstance(default_cleaned_value, enum_class):
                if default_cleaned_value in enum_class.__members__:
                    default_cleaned_value = enum_class[default_cleaned_value]
                else:
                    raise ValueError(
                        '`default_cleaned_value` must be `None` or an instance of `enum_class`')

        super(EnumAttribute, self).__init__(default=default,
                                            default_cleaned_value=default_cleaned_value,
                                            none_value=none_value,
                                            verbose_name=verbose_name, description=description,
                                            primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        if none and not primary:
            self.type = (enum_class, None.__class__)
        else:
            self.type = enum_class
        self.enum_class = enum_class
        self.none = none

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `Enum`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        error = None

        if value and isinstance(value, str):
            try:
                value = self.enum_class[value]
            except KeyError:
                error = 'Value "{}" is not convertible to an instance of {} which contains {}'.format(
                    value, self.enum_class.__name__, list(self.enum_class.__members__.keys()))

        elif isinstance(value, (int, float)):
            try:
                value = self.enum_class(value)
            except ValueError:
                error = 'Value "{}" is not convertible to an instance of {}'.format(
                    value, self.enum_class.__name__)

        elif value is None or value == '':
            value = self.get_default_cleaned_value()

        elif not isinstance(value, self.enum_class):
            error = "Value '{}' must be an instance of `{}` which contains {}".format(
                value, self.enum_class.__name__, list(self.enum_class.__members__.keys()))

        if error:
            return (value, InvalidAttribute(self, [error]))
        else:
            return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        if value is None:
            if not self.none:
                return InvalidAttribute(self, ['Value cannot be `None`'])

        elif not isinstance(value, self.enum_class):
            return InvalidAttribute(self, ["Value '{}' must be an instance of `{}` which contains {}".format(
                value, self.enum_class.__name__, list(self.enum_class.__members__.keys()))])

        return None

    def serialize(self, value):
        """ Serialize enumeration

        Args:
            value (:obj:`Enum`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is not None:
            return value.name
        return ''

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`Enum`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        return value.name

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`Enum`: decoded value of the attribute
        """
        return self.enum_class[json]

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(EnumAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        allowed_values = [val.name for val in self.enum_class]
        if len(','.join(allowed_values)) <= 255:
            validation.type = wc_utils.workbook.io.FieldValidationType.list
            validation.allowed_list_values = allowed_values
        validation.ignore_blank = self.none

        if self.none:
            input_message = ['Select one of "{}" or blank.'.format('", "'.join(allowed_values))]
            error_message = ['Value must be one of "{}" or blank.'.format('", "'.join(allowed_values))]
        else:
            input_message = ['Select one of "{}".'.format('", "'.join(allowed_values))]
            error_message = ['Value must be one of "{}".'.format('", "'.join(allowed_values))]

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: "{}".'.format(default.name))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        serialized_members = []
        for member in self.enum_class.__members__.values():
            serialized_members.append("('{}', {})".format(member.name, member.value.__repr__()))

        return "{}([{}])".format(self.__class__.__name__.rpartition('Attribute')[0],
                                 ", ".join(serialized_members))


class BooleanAttribute(LiteralAttribute):
    """ Boolean attribute

    Attributes:
        default (:obj:`bool`): default value
        default_cleaned_value (:obj:`bool`): value to replace :obj:`None` values with during cleaning
    """

    def __init__(self, default=False, default_cleaned_value=None, none_value=None, verbose_name='', description='Enter a Boolean value'):
        """
        Args:
            default (:obj:`bool`, optional): default value
            default_cleaned_value (:obj:`bool`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description

        Raises:
            :obj:`ValueError`: if `default` is not a `bool` or if `default_cleaned_value` is not a `bool`
        """
        if default is not None and not isinstance(default, bool):
            raise ValueError('`default` must be `None` or an instance of `bool`')
        if default_cleaned_value is not None and not isinstance(default_cleaned_value, bool):
            raise ValueError('`default_cleaned_value` must be `None` or an instance of `bool`')

        super(BooleanAttribute, self).__init__(default=default,
                                               default_cleaned_value=default_cleaned_value,
                                               none_value=none_value,
                                               verbose_name=verbose_name, description=description,
                                               primary=False, unique=False, unique_case_insensitive=False)
        self.type = (bool, None.__class__)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `bool`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value is None:
            value = self.get_default_cleaned_value()
        elif isinstance(value, str):
            if value == '':
                value = None
            elif value in ['true', 'True', 'TRUE', '1']:
                value = True
            elif value in ['false', 'False', 'FALSE', '0']:
                value = False
        else:
            try:
                float_value = float(value)

                if isnan(float_value):
                    value = None
                elif float_value == 0.:
                    value = False
                elif float_value == 1.:
                    value = True
            except Exception:
                pass

        if (value is None) or isinstance(value, bool):
            return (value, None)
        return (value, InvalidAttribute(self, ['Value must be a `bool` or `None`']))

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        if value is not None and not isinstance(value, bool):
            return InvalidAttribute(self, ['Value must be an instance of `bool` or `None`'])

        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(BooleanAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        allowed_values = [True, False]
        validation.type = wc_utils.workbook.io.FieldValidationType.list
        validation.allowed_list_values = allowed_values

        input_message = ['Select "True" or "False".']
        error_message = ['Value must be "True" or "False".']

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: "{}".'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class FloatAttribute(NumericAttribute):
    """ Float attribute

    Attributes:
        default (:obj:`float`): default value
        default_cleaned_value (:obj:`float`): value to replace :obj:`None` values with during cleaning
        min (:obj:`float`): minimum value
        max (:obj:`float`): maximum value
        nan (:obj:`bool`): if true, allow nan values
    """

    def __init__(self, min=float('nan'), max=float('nan'), nan=True,
                 default=float('nan'), default_cleaned_value=float('nan'), none_value=float('nan'), verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            min (:obj:`float`, optional): minimum value
            max (:obj:`float`, optional): maximum value
            nan (:obj:`bool`, optional): if true, allow nan values
            default (:obj:`float`, optional): default value
            default_cleaned_value (:obj:`float`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique

        Raises:
            :obj:`ValueError`: if `max` is less than `min`
        """
        if min is not None:
            min = float(min)
        if max is not None:
            max = float(max)
        if default is not None:
            default = float(default)
        if default_cleaned_value is not None:
            default_cleaned_value = float(default_cleaned_value)
        if not isnan(min) and not isnan(max) and max < min:
            raise ValueError('`max` must be at least `min`')

        super(FloatAttribute, self).__init__(default=default,
                                             default_cleaned_value=default_cleaned_value,
                                             none_value=none_value,
                                             verbose_name=verbose_name, description=description,
                                             primary=primary, unique=unique, unique_case_insensitive=False)

        self.type = float
        self.min = min
        self.max = max
        self.nan = nan

    def value_equal(self, val1, val2, tol=0.):
        """ Determine if attribute values are equal, optionally,
        up to a tolerance

        Args:
            val1 (:obj:`object`): first value
            val2 (:obj:`object`): second value
            tol (:obj:`float`, optional): equality tolerance

        Returns:
            :obj:`bool`: True if attribute values are equal
        """
        return val1 == val2 or \
            (isnan(val1) and isnan(val2)) or \
            (val1 == 0. and abs(val2) < tol) or \
            (val1 != 0. and abs((val1 - val2) / val1) < tol)

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `float`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value is None or (isinstance(value, str) and value == ''):
            value = self.get_default_cleaned_value()

        try:
            value = float(value)
            return (value, None)
        except ValueError:
            return (value, InvalidAttribute(self, ['Value must be a `float`']))

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if isinstance(value, float):
            if not self.nan and isnan(value):
                errors.append('Value cannot be `nan`')

            if (not isnan(self.min)) and (not isnan(value)) and (value < self.min):
                errors.append('Value must be at least {:f}'.format(self.min))

            if (not isnan(self.max)) and (not isnan(value)) and (value > self.max):
                errors.append('Value must be at most {:f}'.format(self.max))
        else:
            errors.append('Value must be an instance of `float`')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize float

        Args:
            value (:obj:`float`): Python representation

        Returns:
            :obj:`float`: simple Python representation
        """
        if isnan(value):
            return None
        return value

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        left_val = getattr(left, self.name)
        right_val = getattr(right, self.name)
        if (not isnan(left_val) or not isnan(right_val)) and left_val != right_val:
            raise ValueError('{}.{} must be equal'.format(left.__class__.__name__, self.name))

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(FloatAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.decimal
        validation.ignore_blank = self.nan
        if self.nan:
            input_message = ['Enter a float or blank.']
            error_message = ['Value must be a float or blank.']
        else:
            input_message = ['Enter a float.']
            error_message = ['Value must be a float.']

        if self.min is None or isnan(self.min):
            if self.max is None or isnan(self.max):
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
                validation.minimum_scalar_value = -1e100
                validation.maximum_scalar_value = 1e100
            else:
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['<=']
                validation.allowed_scalar_value = self.max or 1e-100
                input_message.append('Value must be less than or equal to {}.'.format(self.max))
        else:
            if self.max is None or isnan(self.max):
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
                validation.allowed_scalar_value = self.min or -1e-100
                input_message.append('Value must be greater than or equal to {}.'.format(self.min))
            else:
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
                validation.minimum_scalar_value = self.min or -1e-100
                validation.maximum_scalar_value = self.max or 1e-100
                input_message.append('Value must be between {} and {}.'.format(self.min, self.max))

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None and not isnan(default):
            input_message.append('Default: {}.'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class PositiveFloatAttribute(FloatAttribute):
    """ Positive float attribute """

    def __init__(self, max=float('nan'), nan=True, default=float('nan'), default_cleaned_value=float('nan'),
                 none_value=float('nan'), verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            max (:obj:`float`, optional): maximum value
            nan (:obj:`bool`, optional): if true, allow nan values
            default (:obj:`float`, optional): default value
            default_cleaned_value (:obj:`float`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(PositiveFloatAttribute, self).__init__(min=0., max=max, nan=nan,
                                                     default=default,
                                                     default_cleaned_value=default_cleaned_value,
                                                     none_value=none_value,
                                                     verbose_name=verbose_name, description=description,
                                                     primary=primary, unique=unique)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """

        error = super(PositiveFloatAttribute, self).validate(obj, value)
        if error:
            errors = error.messages
        else:
            errors = []

        if not isnan(value) and value <= 0:
            errors.append('Value must be positive')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(FloatAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.decimal
        validation.ignore_blank = self.nan
        if self.nan:
            input_message = ['Enter a float or blank.']
            error_message = ['Value must be a float or blank.']
        else:
            input_message = ['Enter a float.']
            error_message = ['Value must be a float.']

        if self.max is None or isnan(self.max):
            validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
            validation.allowed_scalar_value = -1e-100
            input_message.append('Value must be positive.')
        else:
            validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
            validation.minimum_scalar_value = -1e-100
            validation.maximum_scalar_value = self.max or 1e-100
            input_message.append('Value must be positive and less than or equal to {}.'.format(self.max))

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None and not isnan(default):
            input_message.append('Default: {}.'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class IntegerAttribute(NumericAttribute):
    """ Integer attribute

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
        default (:obj:`int`): default value
        default_cleaned_value (:obj:`int`): value to replace :obj:`None` values with during cleaning
        min (:obj:`int`): minimum value
        max (:obj:`int`): maximum value
    """

    def __init__(self, min=None, max=None, none=False, default=None, default_cleaned_value=None,
                 none_value=None, verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            min (:obj:`int`, optional): minimum value
            max (:obj:`int`, optional): maximum value
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`int`, optional): default value
            default_cleaned_value (:obj:`int`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique

        Raises:
            :obj:`ValueError`: if `max` is less than `min`
        """
        if min is not None:
            min = int(min)
        if max is not None:
            max = int(max)
        if default is not None:
            default = int(default)
        if default_cleaned_value is not None:
            default_cleaned_value = int(default_cleaned_value)
        if min is not None and max is not None and max < min:
            raise ValueError('`max` must be at least `min`')

        super(IntegerAttribute, self).__init__(default=default,
                                               default_cleaned_value=default_cleaned_value,
                                               none_value=none_value,
                                               verbose_name=verbose_name, description=description,
                                               primary=primary, unique=unique, unique_case_insensitive=False)

        if none and not primary:
            self.type = (int, None.__class__)
        else:
            self.type = int
        self.none = none
        self.min = min
        self.max = max

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `int`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """

        if value is None or (isinstance(value, str) and value == ''):
            return (self.get_default_cleaned_value(), None, )

        try:
            if float(value) == int(float(value)):
                return (int(float(value)), None, )
        except ValueError:
            pass
        return (value, InvalidAttribute(self, ['Value must be an integer']), )

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, otherwise return list of
                errors as an instance of `InvalidAttribute`
        """
        errors = []

        if self.none and value is None:
            pass
        if isinstance(value, int):
            if self.min is not None:
                if value < self.min:
                    errors.append(
                        'Value must be at least {:d}'.format(self.min))

            if self.max is not None:
                if value > self.max:
                    errors.append(
                        'Value must be at most {:d}'.format(self.max))

        elif value is not None:
            errors.append('Value must be an instance of `int` or `None`')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize integer

        Args:
            value (:obj:`int`): Python representation

        Returns:
            :obj:`float`: simple Python representation
        """
        if value is None:
            return None
        return float(value)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`int`): value of the attribute

        Returns:
            :obj:`float`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        return float(value)

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`float`): simple Python representation of a value of the attribute

        Returns:
            :obj:`int`: decoded value of the attribute
        """
        if json is None:
            return None
        return int(json)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(IntegerAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.integer
        input_message = ['Enter an integer.']
        error_message = ['Value must be an integer.']

        if self.min is None or isnan(self.min):
            if self.max is None or isnan(self.max):
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
                validation.minimum_scalar_value = -2**15
                validation.maximum_scalar_value = 2**15 - 1
            else:
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['<=']
                validation.allowed_scalar_value = self.max or 1e-100
                input_message.append('Value must be less than or equal to {}.'.format(self.max))
        else:
            if self.max is None or isnan(self.max):
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
                validation.allowed_scalar_value = self.min or -1e-100
                input_message.append('Value must be greater than or equal to {}.'.format(self.min))
            else:
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
                validation.minimum_scalar_value = self.min or -1e-100
                validation.maximum_scalar_value = self.max or 1e-100
                input_message.append('Value must be between {} and {}.'.format(self.min, self.max))

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None and not isnan(default):
            input_message.append('Default: {}.'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class PositiveIntegerAttribute(IntegerAttribute):
    """ Positive integer attribute """

    def __init__(self, max=None, none=False, default=None, default_cleaned_value=None,
                 none_value=None, verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            min (:obj:`int`, optional): minimum value
            max (:obj:`int`, optional): maximum value
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`int`, optional): default value
            default_cleaned_value (:obj:`int`, optional): value to replace :obj:`None` values with during cleaning
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(PositiveIntegerAttribute, self).__init__(min=0, max=max,
                                                       none=none, default=default,
                                                       default_cleaned_value=default_cleaned_value,
                                                       none_value=none_value,
                                                       verbose_name=verbose_name, description=description,
                                                       primary=primary, unique=unique)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """

        error = super(PositiveIntegerAttribute, self).validate(obj, value)
        if error:
            errors = error.messages
        else:
            errors = []

        if (value is not None) and (float(value) <= 0):
            errors.append('Value must be positive')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(IntegerAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.integer
        input_message = ['Enter an integer.']
        error_message = ['Value must be an integer.']

        if self.max is None or isnan(self.max):
            validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
            validation.allowed_scalar_value = 1
            input_message.append('Value must be positive.')
        else:
            validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
            validation.minimum_scalar_value = -1e-100
            validation.maximum_scalar_value = self.max or 1e-100
            input_message.append('Value must be positive and less than or equal to {}.'.format(self.max))

        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None and not isnan(default):
            input_message.append('Default: {}.'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class StringAttribute(LiteralAttribute):
    """ String attribute

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
        default (:obj:`str`): default value
        default_cleaned_value (:obj:`str`): value to replace :obj:`None` values with during cleaning
        min_length (:obj:`int`): minimum length
        max_length (:obj:`int`): maximum length
    """

    def __init__(self, min_length=0, max_length=255, none=False, default='', default_cleaned_value='', none_value='',
                 verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`str`, optional): default value
            default_cleaned_value (:obj:`str`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness

        Raises:
            :obj:`ValueError`: if `min_length` is negative, `max_length` is less than `min_length`,
                `default` is not a string, or `default_cleaned_value` is not a string
        """

        if not isinstance(min_length, int) or min_length < 0:
            raise ValueError('`min_length` must be a non-negative integer')
        if (max_length is not None) and (not isinstance(max_length, int) or max_length < min_length):
            raise ValueError('`max_length` must be at least `min_length` or `None`')
        if default is not None and not isinstance(default, str):
            raise ValueError('`default` must be a string')
        if default_cleaned_value is not None and not isinstance(default_cleaned_value, str):
            raise ValueError('`default_cleaned_value` must be a string')

        super(StringAttribute, self).__init__(default=default,
                                              default_cleaned_value=default_cleaned_value,
                                              none_value=none_value,
                                              verbose_name=verbose_name, description=description,
                                              primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)

        if none and not primary:
            self.type = (str, None.__class__)
        else:
            self.type = str
        self.min_length = min_length
        self.max_length = max_length
        self.none = none

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `str`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value is None:
            value = self.get_default_cleaned_value()
        elif not isinstance(value, str):
            value = str(value)
        return (value, None)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value for this StringAttribute

        Args:
            obj (:obj:`Model`): class being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if self.none and value is None:
            pass
        elif not isinstance(value, str):
            errors.append('Value must be an instance of `str`')
        else:
            if self.min_length and len(value) < self.min_length:
                errors.append(
                    'Value must be at least {:d} characters'.format(self.min_length))

            if self.max_length and len(value) > self.max_length:
                errors.append(
                    'Value must be less than {:d} characters'.format(self.max_length))

            if self.primary and (value == '' or value is None):
                errors.append('{} value for primary attribute cannot be empty'.format(
                    self.__class__.__name__))

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`str`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        return value

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(StringAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        input_message = ['Enter a string.']
        error_message = ['Value must be a string.']
        if self.min_length is not None and self.min_length:
            if self.max_length is not None:
                validation.type = wc_utils.workbook.io.FieldValidationType.length
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['between']
                validation.minimum_scalar_value = self.min_length
                validation.maximum_scalar_value = self.max_length
                validation.ignore_blank = False
                input_message.append('Value must be between {} and {} characters.'.format(self.min_length, self.max_length))
                error_message.append('Value must be between {} and {} characters.'.format(self.min_length, self.max_length))
            else:
                validation.type = wc_utils.workbook.io.FieldValidationType.length
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
                validation.allowed_scalar_value = self.min_length
                validation.ignore_blank = False
                input_message.append('Value must at least {} characters.'.format(self.min_length))
                error_message.append('Value must at least {} characters.'.format(self.min_length))
        elif self.max_length is not None:
            validation.type = wc_utils.workbook.io.FieldValidationType.length
            validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['<=']
            validation.allowed_scalar_value = self.max_length
            input_message.append('Value must be less than or equal to {} characters.'.format(self.max_length))
            error_message.append('Value must be less than or equal to {} characters.'.format(self.max_length))
        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: "{}".'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        args = []
        if self.primary:
            args.append('primary=True')
        if self.unique:
            args.append('unique=True')

        return "{}{}".format(self.__class__.__name__.rpartition('Attribute')[0],
                             "({})".format(", ".join(args)) if args else "")


class LongStringAttribute(StringAttribute):
    """ Long string attribute """

    def __init__(self, min_length=0, max_length=2**32 - 1, default='', default_cleaned_value='', none_value='',
                 verbose_name='', description='',
                 primary=False, unique=False, unique_case_insensitive=False):
        """
        Args:
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            default (:obj:`str`, optional): default value
            default_cleaned_value (:obj:`str`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
            unique_case_insensitive (:obj:`bool`, optional): if true, conduct case-insensitive test of uniqueness
        """

        super(LongStringAttribute, self).__init__(min_length=min_length, max_length=max_length,
                                                  default=default,
                                                  default_cleaned_value=default_cleaned_value,
                                                  none_value=none_value,
                                                  verbose_name=verbose_name, description=description,
                                                  primary=primary, unique=unique, unique_case_insensitive=unique_case_insensitive)


class RegexAttribute(StringAttribute):
    """ Regular expression attribute

    Attributes:
        pattern (:obj:`str`): regular expression pattern
        flags (:obj:`int`): regular expression flags
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
    """

    def __init__(self, pattern, flags=0, min_length=0, max_length=None,
                 none=False, default='', default_cleaned_value='',
                 none_value='', verbose_name='', description='',
                 primary=False, unique=False):
        """
        Args:
            pattern (:obj:`str`): regular expression pattern
            flags (:obj:`int`, optional): regular expression flags
            min_length (:obj:`int`, optional): minimum length
            max_length (:obj:`int`, optional): maximum length
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`str`, optional): default value
            default_cleaned_value (:obj:`str`, optional): value to replace :obj:`None` values with during cleaning
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """

        unique_case_insensitive = bin(flags)[-2] == '1'
        super(RegexAttribute, self).__init__(min_length=min_length, max_length=max_length,
                                             none=none, default=default,
                                             default_cleaned_value=default_cleaned_value,
                                             none_value=none_value,
                                             verbose_name=verbose_name, description=description,
                                             primary=primary, unique=unique,
                                             unique_case_insensitive=unique_case_insensitive)
        self.pattern = pattern
        self.flags = flags

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`object`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = super(RegexAttribute, self).validate(obj, value)
        if errors:
            errors = errors.messages
        else:
            errors = []

        if not ((self.none and value is None) or
                (isinstance(value, str) and re.search(self.pattern, value, flags=self.flags))):
            errors.append("Value '{}' does not match pattern: {}".format(
                value, self.pattern))

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        args = []
        args.append(self.pattern.__repr__())
        if self.flags:
            args.append('flags={}'.format(self.flags))
        if self.primary:
            args.append('primary=True')
        if self.unique:
            args.append('unique=True')

        return "{}{}".format(self.__class__.__name__.rpartition('Attribute')[0],
                             "({})".format(", ".join(args)) if args else "")


class SlugAttribute(RegexAttribute):
    """ Slug attribute to be used for string IDs """

    def __init__(self, verbose_name='', description=None, primary=True, unique=True):
        """
        Args:
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate whether attribute must be unique
        """
        if description is None:
            description = ("Enter a unique string identifier that "
                           "(a) is composed of letters, numbers and underscores; "
                           "(b) is 90 characters or less; and "
                           "(c) is not a decimal, hexadecimal, or scientific number")

        super(SlugAttribute, self).__init__(pattern=(r'^(?!(^|\b)'
                                                     r'(\d+(\.\d*)?(\b|$))'
                                                     r'|(\.\d+$)'
                                                     r'|(0[x][0-9a-f]+(\b|$))'
                                                     r'|([0-9]+e[0-9]+(\b|$))'
                                                     r')'
                                                     r'[a-z0-9_]+$'),
                                            flags=re.I,
                                            min_length=1, max_length=90,
                                            verbose_name=verbose_name, description=description,
                                            primary=primary, unique=unique)


class UrlAttribute(RegexAttribute):
    """ URL attribute to be used for URLs """

    def __init__(self, verbose_name='', description='Enter a valid URL', primary=False, unique=False):
        """
        Args:
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        core_pattern = (r'(?:http|ftp)s?://'
                        r'(?:'
                        r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
                        r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                        r')'
                        r'(?::\d+)?'
                        r'(?:/?|[/?]\S+)')
        pattern = r'^(|{})$'.format(core_pattern)

        super(UrlAttribute, self).__init__(pattern=pattern,
                                           flags=re.I,
                                           min_length=0, max_length=2**16 - 1,
                                           verbose_name=verbose_name, description=description,
                                           primary=primary, unique=unique)

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        args = []
        if self.primary:
            args.append('primary=True')
        if self.unique:
            args.append('unique=True')

        return "{}{}".format(self.__class__.__name__.rpartition('Attribute')[0],
                             "({})".format(", ".join(args)) if args else "")


class EmailAttribute(StringAttribute):
    """ Attribute for email addresses """

    def __init__(self, verbose_name='', description='Enter a valid email address', primary=False, unique=False):
        """
        Args:
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(EmailAttribute, self).__init__(verbose_name=verbose_name, description=description,
                                             primary=primary, unique=unique)

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`date`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        error = super(EmailAttribute, self).validate(obj, value)
        if error:
            errors = error.messages
        else:
            errors = []

        if not validate_email.validate_email(value):
            errors.append('Value must be a valid email address')

        if errors:
            return InvalidAttribute(self, errors)
        return None


class DateAttribute(LiteralAttribute):
    """ Date attribute

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
        default (:obj:`date`): default date
        default_cleaned_value (:obj:`date`): value to replace
            :obj:`None` values with during cleaning, or function
            which computes the value to replace :obj:`None` values
    """

    def __init__(self, none=True, default=None, default_cleaned_value=None, none_value=None,
                 verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`date`, optional): default date
            default_cleaned_value (:obj:`date`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(DateAttribute, self).__init__(default=default,
                                            default_cleaned_value=default_cleaned_value,
                                            none_value=none_value,
                                            verbose_name=verbose_name, description=description,
                                            primary=primary, unique=unique)
        if none and not primary:
            self.type = (date, None.__class__)
        else:
            self.type = date
        self.none = none

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple`: (`date`, `None`), or (`None`, `InvalidAttribute`) reporting error
        """
        if value in (None, ''):
            return (self.get_default_cleaned_value(), None)

        if isinstance(value, datetime):
            if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
                return (value.date(), None)
            else:
                return (value, InvalidAttribute(self, ['Time must be 0:0:0.0']))

        if isinstance(value, date):
            return (value, None)

        if isinstance(value, str):
            try:
                datetime_value = dateutil.parser.parse(value)
                if datetime_value.hour == 0 and \
                        datetime_value.minute == 0 and \
                        datetime_value.second == 0 and \
                        datetime_value.microsecond == 0:
                    return (datetime_value.date(), None)
                else:
                    return (value, InvalidAttribute(self, ['Time must be 0:0:0.0']))
            except ValueError:
                return (value, InvalidAttribute(self, ['String must be a valid date']))

        try:
            float_value = float(value)
            int_value = int(float_value)
            if float_value == int_value:
                return (date.fromordinal(int_value + date(1900, 1, 1).toordinal() - 1), None)
        except (TypeError, ValueError):
            pass

        return (value, InvalidAttribute(self, ['Value must be an instance of `date`']))

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`date`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if not self.none:
                errors.append('Value cannot be `None`')
        elif isinstance(value, date):
            if value.year < 1900 or value.year > 10000:
                errors.append('Year must be between 1900 and 9999')
        else:
            errors.append('Value must be an instance of `date`')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`date`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''
        return '{0:04d}-{1:02d}-{2:02d}'.format(value.year, value.month, value.day)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`date`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        return value.strftime('%Y-%m-%d')

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`date`: decoded value of the attribute
        """
        if json is None:
            return None
        return datetime.strptime(json, '%Y-%m-%d').date()

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(DateAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.date
        validation.criterion = wc_utils.workbook.io.FieldValidationCriterion.between
        validation.minimum_scalar_value = date(1900, 1, 1)
        validation.maximum_scalar_value = date(9999, 12, 31)

        input_message = ['Enter a date.']
        error_message = ['Value must be a date.']
        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: "{}".'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class TimeAttribute(LiteralAttribute):
    """ Time attribute

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
        default (:obj:`time`): default time
        default_cleaned_value (:obj:`time`): value to replace
            :obj:`None` values with during cleaning, or function
            which computes the value to replace :obj:`None` values
    """

    def __init__(self, none=True, default=None, default_cleaned_value=None, none_value=None,
                 verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`time`, optional): default time
            default_cleaned_value (:obj:`time`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(TimeAttribute, self).__init__(default=default,
                                            default_cleaned_value=default_cleaned_value,
                                            none_value=none_value,
                                            verbose_name=verbose_name, description=description,
                                            primary=primary, unique=unique)
        if none and not primary:
            self.type = (time, None.__class__)
        else:
            self.type = time
        self.none = none

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `time`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if value in (None, ''):
            return (self.get_default_cleaned_value(), None)

        if isinstance(value, time):
            return (value, None)

        if isinstance(value, str):
            if re.match(r'^\d{1,2}:\d{1,2}(:\d{1,2})*$', value):
                try:
                    datetime_value = dateutil.parser.parse(value)
                    return (datetime_value.time(), None)
                except ValueError:
                    return (value, InvalidAttribute(self, ['String must be a valid time']))
            else:
                return (value, InvalidAttribute(self, ['String must be a valid time']))

        try:
            int_value = round(float(value) * 24 * 60 * 60)
            if int_value < 0 or int_value > 24 * 60 * 60 - 1:
                return (value, InvalidAttribute(self, ['Number must be a valid time']))

            hour = int(int_value / (60. * 60.))
            minutes = int((int_value - hour * 60. * 60.) / 60.)
            seconds = int(int_value % 60)
            return (time(hour, minutes, seconds), None)
        except (TypeError, ValueError):
            pass

        return (value, InvalidAttribute(self, ['Value must be an instance of `time`']))

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`time`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if not self.none:
                errors.append('Value cannot be `None`')
        elif isinstance(value, time):
            if value.microsecond != 0:
                errors.append('Microsecond must be 0')
        else:
            errors.append('Value must be an instance of `time`')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`time`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''
        return '{0:02d}:{1:02d}:{2:02d}'.format(value.hour, value.minute, value.second)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`time`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        return value.strftime('%H:%M:%S')

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`time`: decoded value of the attribute
        """
        if json is None:
            return None
        return datetime.strptime(json, '%H:%M:%S').time()

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(TimeAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.time
        validation.criterion = wc_utils.workbook.io.FieldValidationCriterion.between
        validation.minimum_scalar_value = time(0, 0, 0, 0)
        validation.maximum_scalar_value = time(23, 59, 59, 999999)

        input_message = ['Enter a time.']
        error_message = ['Value must be a time.']
        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: "{}".'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class DateTimeAttribute(LiteralAttribute):
    """ Datetime attribute

    Attributes:
        none (:obj:`bool`): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
        default (:obj:`datetime`): default datetime
        default_cleaned_value (:obj:`datetime`): value to replace
            :obj:`None` values with during cleaning, or function
            which computes the value to replace :obj:`None` values
    """

    def __init__(self, none=True, default=None, default_cleaned_value=None, none_value=None,
                 verbose_name='', description='', primary=False, unique=False):
        """
        Args:
            none (:obj:`bool`, optional): if :obj:`False`, the attribute is invalid if its value is :obj:`None`
            default (:obj:`datetime`, optional): default datetime
            default_cleaned_value (:obj:`datetime`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            none_value (:obj:`object`, optional): none value
            verbose_name (:obj:`str`, optional): verbose name
            description (:obj:`str`, optional): description
            primary (:obj:`bool`, optional): indicate if attribute is primary attribute
            unique (:obj:`bool`, optional): indicate if attribute value must be unique
        """
        super(DateTimeAttribute, self).__init__(default=default,
                                                default_cleaned_value=default_cleaned_value,
                                                none_value=none_value,
                                                verbose_name=verbose_name, description=description,
                                                primary=primary, unique=unique)
        if none and not primary:
            self.type = (datetime, None.__class__)
        else:
            self.type = datetime
        self.none = none

    def clean(self, value):
        """ Convert attribute value into the appropriate type

        Args:
            value (:obj:`object`): value of attribute to clean

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` if `value` is invalid, or
            :obj:`tuple` of `datetime`, `None` with cleaned value otherwise
        """
        if value in (None, ''):
            return (self.get_default_cleaned_value(), None)

        if isinstance(value, datetime):
            return (value, None)

        if isinstance(value, date):
            return (datetime.combine(value, time(0, 0, 0, 0)), None)

        if isinstance(value, str):
            try:
                return (dateutil.parser.parse(value), None)
            except ValueError:
                return (value, InvalidAttribute(self, ['String must be a valid datetime']))

        try:
            float_value = float(value)
            date_int_value = int(float_value)
            time_int_value = round((float_value % 1) * 24 * 60 * 60)
            if time_int_value == 24 * 60 * 60:
                time_int_value = 0
                date_int_value += 1

            date_value = date.fromordinal(
                date_int_value + date(1900, 1, 1).toordinal() - 1)

            hour = int(time_int_value / (60. * 60.))
            minutes = int((time_int_value - hour * 60. * 60.) / 60.)
            seconds = int(time_int_value % 60)
            time_value = time(hour, minutes, seconds)

            return (datetime.combine(date_value, time_value), None)
        except (TypeError, ValueError):
            pass

        return (value, InvalidAttribute(self, ['Value must be an instance of `datetime`']))

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`datetime`): value of attribute to validate

        Returns:
            :obj:`None` or `InvalidAttribute`: `None` if attribute is valid, otherwise return list of
            errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if not self.none:
                errors.append('Value cannot be `None`')
        elif isinstance(value, datetime):
            if value.year < 1900 or value.year > 10000:
                errors.append('Year must be between 1900 and 9999')
            if value.microsecond != 0:
                errors.append('Microsecond must be 0')
        else:
            errors.append('Value must be an instance of `datetime`')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def serialize(self, value):
        """ Serialize string

        Args:
            value (:obj:`datetime`): Python representation

        Returns:
            :obj:`str`: simple Python representation
        """
        if value is None:
            return ''

        date_value = value.date()
        time_value = value.time()

        return '{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:{5:02d}'.format(
            date_value.year, date_value.month, date_value.day,
            time_value.hour, time_value.minute, time_value.second)

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`datetime`): value of the attribute

        Returns:
            :obj:`str`: simple Python representation of a value of the attribute
        """
        if value is None:
            return None
        return value.strftime('%Y-%m-%d %H:%M:%S')

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`str`): simple Python representation of a value of the attribute

        Returns:
            :obj:`datetime`: decoded value of the attribute
        """
        if json is None:
            return None
        return datetime.strptime(json, '%Y-%m-%d %H:%M:%S')

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        validation = super(DateTimeAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        validation.type = wc_utils.workbook.io.FieldValidationType.date
        validation.criterion = wc_utils.workbook.io.FieldValidationCriterion.between
        validation.minimum_scalar_value = datetime(1900, 1, 1, 0, 0, 0, 0)
        validation.maximum_scalar_value = datetime(999, 12, 31, 23, 59, 59, 999999)

        input_message = ['Enter a date and time.']
        error_message = ['Value must be a date and time.']
        if self.unique:
            input_message.append('Value must be unique.')
            error_message.append('Value must be unique.')

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: "{}".'.format(default))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class RelatedManager(list):
    """ Represent values and related values of related attributes

    Attributes:
        object (:obj:`Model`): model instance
        attribute (:obj:`Attribute`): attribute
        related (:obj:`bool`): is related attribute
    """

    def __init__(self, object, attribute, related=True):
        """
        Args:
            object (:obj:`Model`): model instance
            attribute (:obj:`Attribute`): attribute
            related (:obj:`bool`, optional): is related attribute
        """
        super(RelatedManager, self).__init__()
        self.object = object
        self.attribute = attribute
        self.related = related

    def create(self, __type=None, **kwargs):
        """ Create instance of primary class and add to list

        Args:
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            **kwargs: dictionary of attribute name/value pairs

        Returns:
            :obj:`Model`: created object

        Raises:
            :obj:`ValueError`: if keyword argument is not an attribute of the class
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        if self.related:
            if self.attribute.name in kwargs:
                raise TypeError("'{}' is an invalid keyword argument for {}.create for {}".format(
                    self.attribute.name, self.__class__.__name__, self.attribute.primary_class.__name__))
            cls = __type or self.attribute.primary_class
            obj = cls(**kwargs)

        else:
            if self.attribute.related_name in kwargs:
                raise TypeError("'{}' is an invalid keyword argument for {}.create for {}".format(
                    self.attribute.related_name, self.__class__.__name__, self.attribute.primary_class.__name__))
            cls = __type or self.attribute.related_class
            obj = cls(**kwargs)

        self.append(obj)

        return obj

    def append(self, value, **kwargs):
        """ Add value to list

        Args:
            value (:obj:`object`): value

        Returns:
            :obj:`RelatedManager`: self
        """
        super(RelatedManager, self).append(value, **kwargs)

        return self

    def add(self, value, **kwargs):
        """ Add value to list

        Args:
            value (:obj:`object`): value

        Returns:
            :obj:`RelatedManager`: self
        """
        self.append(value, **kwargs)

        return self

    def discard(self, value):
        """ Remove value from list if value in list

        Args:
            value (:obj:`object`): value

        Returns:
            :obj:`RelatedManager`: self
        """
        if value in self:
            self.remove(value)

        return self

    def clear(self):
        """ Remove all elements from list

        Returns:
            :obj:`RelatedManager`: self
        """
        for value in reversed(self):
            self.remove(value)

        return self

    def pop(self, i=-1):
        """ Remove an arbitrary element from the list

        Args:
            i (:obj:`int`, optional): index of element to remove

        Returns:
            :obj:`object`: removed element
        """
        value = super(RelatedManager, self).pop(i)
        self.remove(value, update_list=False)

        return value

    def update(self, values):
        """ Add values to list

        Args:
            values (:obj:`list`): values to add to list

        Returns:
            :obj:`RelatedManager`: self
        """
        self.extend(values)

        return self

    def extend(self, values):
        """ Add values to list

        Args:
            values (:obj:`list`): values to add to list

        Returns:
            :obj:`RelatedManager`: self
        """
        for value in values:
            self.append(value)

        return self

    def intersection_update(self, values):
        """ Retain only intersection of list and `values`

        Args:
            values (:obj:`list`): values to intersect with list

        Returns:
            :obj:`RelatedManager`: self
        """
        for value in reversed(self):
            if value not in values:
                self.remove(value)

        return self

    def difference_update(self, values):
        """ Retain only values of list not in `values`

        Args:
            values (:obj:`list`): values to difference with list

        Returns:
            :obj:`RelatedManager`: self
        """
        for value in values:
            if value in self:
                self.remove(value)

        return self

    def symmetric_difference_update(self, values):
        """ Retain values in only one of list and `values`

        Args:
            values (:obj:`list`): values to difference with list

        Returns:
            :obj:`RelatedManager`: self
        """
        self_copy = copy.copy(self)
        values_copy = copy.copy(values)

        for value in values_copy:
            if value in self_copy:
                self.remove(value)
            else:
                self.add(value)

        return self

    def get_or_create(self, __type=None, **kwargs):
        """ Get or create a related object by attribute/value pairs. Optionally, only get or create instances of
        :obj:`Model` subclass :obj:`__type`.

        Args:
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            **kwargs: dictionary of attribute name/value pairs to find matching
                object or create new object

        Returns:
            :obj:`Model`: existing or new object
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        obj = self.get_one(__type=__type, **kwargs)
        if obj:
            return obj
        else:
            return self.create(__type=__type, **kwargs)

    def get_one(self, __type=None, **kwargs):
        """ Get a related object by attribute/value pairs; report an error if multiple objects match and,
        optionally, only return matches that are also instances of :obj:`Model` subclass :obj:`__type`.

        Args:
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            **kwargs: dictionary of attribute name/value pairs to find matching
                objects

        Returns:
            :obj:`Model` or `None`: matching instance of `Model`, or `None` if no matching instance

        Raises:
            :obj:`ValueError`: if multiple matching objects
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        matches = self.get(__type=__type, **kwargs)

        if len(matches) == 0:
            return None

        if len(matches) == 1:
            return matches.pop()

        if len(matches) > 1:
            raise ValueError(
                'Multiple objects match the attribute name/value pair(s)')

    def get(self, __type=None, **kwargs):
        """ Get related objects by attribute/value pairs and, optionally, only return matches that are also
        instances of :obj:`Model` subclass :obj:`__type`.

        Args:
            __type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): subclass(es) of :obj:`Model`
            **kwargs: dictionary of attribute name/value pairs to find matching
                objects

        Returns:
            :obj:`list` of :obj:`Model`: matching instances of `Model`
        """
        if '__type' in kwargs:
            __type = kwargs.pop('__type')

        matches = []
        for obj in self:
            if obj.has_attr_vals(__type=__type, __check_attr_defined=False, **kwargs):
                matches.append(obj)
        return matches

    def index(self, *args, **kwargs):
        """ Get related object index by attribute/value pairs

        Args:
            *args (:obj:`Model`): object to find
            **kwargs: dictionary of attribute name/value pairs to find matching objects

        Returns:
            :obj:`int`: index of matching object

        Raises:
            :obj:`ValueError`: if no argument or keyword argument is provided, if argument and keyword arguments are
                both provided, if multiple arguments are provided, if the keyword attribute/value pairs match no object,
                or if the keyword attribute/value pairs match multiple objects
        """
        if args and kwargs:
            raise ValueError('Argument and keyword arguments cannot both be provided')
        if not args and not kwargs:
            raise ValueError('At least one argument must be provided')

        if args:
            if len(args) > 1:
                raise ValueError('At most one argument can be provided')

            return super(RelatedManager, self).index(args[0])

        else:
            match = None

            for i_obj, obj in enumerate(self):
                is_match = True
                for attr_name, value in kwargs.items():
                    if getattr(obj, attr_name) != value:
                        is_match = False
                        break

                if is_match:
                    if match is not None:
                        raise ValueError(
                            'Keyword argument attribute/value pairs match multiple objects')
                    else:
                        match = i_obj

            if match is None:
                raise ValueError('No matching object with {}'.format(', '.join(str(k) + '=' + str(v) for k, v in kwargs.items())))

            return match


class ManyToOneRelatedManager(RelatedManager):
    """ Represent values of related attributes """

    def __init__(self, object, attribute):
        """
        Args:
            object (:obj:`Model`): model instance
            attribute (:obj:`Attribute`): attribute
        """
        super(ManyToOneRelatedManager, self).__init__(
            object, attribute, related=True)

    def append(self, value, propagate=True):
        """ Add value to list

        Args:
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if value in self:
            return self

        super(ManyToOneRelatedManager, self).append(value)
        if propagate:
            value.__setattr__(self.attribute.name, self.object, propagate=True)

        return self

    def remove(self, value, update_list=True, propagate=True):
        """ Remove value from list

        Args:
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if update_list:
            super(ManyToOneRelatedManager, self).remove(value)
        if propagate:
            value.__setattr__(self.attribute.name, None, propagate=False)

        return self

    def cut(self, kind=None):
        """ Cut values and their children of kind :obj:`kind` into separate graphs.

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to include

        Returns:
            :obj:`list` of :obj:`Model`: cut values and their children
        """
        objs = []
        for obj in self:
            obj = obj.copy()
            obj.cut(kind=kind)
            objs.append(obj)
        return objs


class OneToManyRelatedManager(RelatedManager):
    """ Represent values of related attributes """

    def __init__(self, object, attribute):
        """
        Args:
            object (:obj:`Model`): model instance
            attribute (:obj:`Attribute`): attribute
        """
        super(OneToManyRelatedManager, self).__init__(
            object, attribute, related=False)

    def append(self, value, propagate=True):
        """ Add value to list

        Args:
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if value in self:
            return self

        super(OneToManyRelatedManager, self).append(value)
        if propagate:
            value.__setattr__(self.attribute.related_name,
                              self.object, propagate=True)

        return self

    def remove(self, value, update_list=True, propagate=True):
        """ Remove value from list

        Args:
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if update_list:
            super(OneToManyRelatedManager, self).remove(value)
        if propagate:
            value.__setattr__(self.attribute.related_name,
                              None, propagate=False)

        return self

    def cut(self, kind=None):
        """ Cut values and their children of kind :obj:`kind` into separate graphs.

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to include

        Returns:
            :obj:`list` of :obj:`Model`: cut values and their children
        """
        objs = []
        for obj in self:
            obj = obj.copy()
            obj.cut(kind=kind)
            objs.append(obj)
        return objs


class ManyToManyRelatedManager(RelatedManager):
    """ Represent values and related values of related attributes """

    def append(self, value, propagate=True):
        """ Add value to list

        Args:
            value (:obj:`object`): value
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if value in self:
            return self

        super(ManyToManyRelatedManager, self).append(value)
        if propagate:
            if self.related:
                getattr(value, self.attribute.name).append(
                    self.object, propagate=False)
            else:
                getattr(value, self.attribute.related_name).append(
                    self.object, propagate=False)

        return self

    def remove(self, value, update_list=True, propagate=True):
        """ Remove value from list

        Args:
            value (:obj:`object`): value
            update_list (:obj:`bool`, optional): update list
            propagate (:obj:`bool`, optional): propagate change to related attribute

        Returns:
            :obj:`RelatedManager`: self
        """
        if update_list:
            super(ManyToManyRelatedManager, self).remove(value)
        if propagate:
            if self.related:
                getattr(value, self.attribute.name).remove(
                    self.object, propagate=False)
            else:
                getattr(value, self.attribute.related_name).remove(
                    self.object, propagate=False)

        return self

    def cut(self, kind=None):
        """ Cut values and their children of kind :obj:`kind` into separate graphs.

        If :obj:`kind` is :obj:`None`, children are defined to be the values of the related attributes defined
        in each class.

        Args:
            kind (:obj:`str`, optional): kind of children to include

        Returns:
            :obj:`list` of :obj:`Model`: cut values and their children
        """
        objs = []
        for obj in self:
            obj = obj.copy()
            obj.cut(kind=kind)
            objs.append(obj)
        return objs


class RelatedAttribute(Attribute):
    """ Attribute which represents a relationship with other `Model`\(s)

    Attributes:
        related_type (:obj:`types.TypeType` or :obj:`tuple` of :obj:`types.TypeType`): allowed
            type(s) of the related values of the attribute
        primary_class (:obj:`class`): the type of the class that this related attribute references
        related_class (:obj:`class`): the type of the class that contains a related attribute
        related_name (:obj:`str`): name of related attribute on `related_class`
        verbose_related_name (:obj:`str`): verbose related name
        related_init_value (:obj:`object`): initial value of related attribute
        related_default (:obj:`object`): default value of related attribute
        min_related (:obj:`int`): minimum number of related objects in the forward direction
        max_related (:obj:`int`): maximum number of related objects in the forward direction
        min_related_rev (:obj:`int`): minimum number of related objects in the reverse direction
        max_related_rev (:obj:`int`): maximum number of related objects in the reverse direction
    """

    def __init__(self, related_class, related_name='',
                 init_value=None, default=None, default_cleaned_value=None, none_value=None,
                 related_init_value=None, related_default=None,
                 min_related=0, max_related=float('inf'), min_related_rev=0, max_related_rev=float('inf'),
                 verbose_name='', verbose_related_name='', description=''):
        """
        Args:
            related_class (:obj:`class`): related class
            related_name (:obj:`str`, optional): name of related attribute on `related_class`
            init_value (:obj:`object`, optional): initial value
            default (:obj:`object`, optional): default value
            default_cleaned_value (:obj:`object`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            none_value (:obj:`object`, optional): none value
            related_init_value (:obj:`object`, optional): related initial value
            related_default (:obj:`object`, optional): related default value
            min_related (:obj:`int`, optional): minimum number of related objects in the forward direction
            max_related (:obj:`int`, optional): maximum number of related objects in the forward direction
            min_related_rev (:obj:`int`, optional): minimum number of related objects in the reverse direction
            max_related_rev (:obj:`int`, optional): maximum number of related objects in the reverse direction
            verbose_name (:obj:`str`, optional): verbose name
            verbose_related_name (:obj:`str`, optional): verbose related name
            description (:obj:`str`, optional): description

        Raises:
            :obj:`ValueError`: If default or related_default is not None, an empty list, or a callable or
                default and related_default are both non-empty lists or callables
        """

        if default is not None and not isinstance(default, list) and not callable(default):
            raise ValueError('`default` must be `None`, a list, or a callable')

        if default_cleaned_value is not None and \
                not isinstance(default_cleaned_value, list) and \
                not callable(default_cleaned_value):
            raise ValueError('`default_cleaned_value` must be `None`, a list, or a callable')

        if related_default is not None and not isinstance(related_default, list) and not callable(related_default):
            raise ValueError('Related default must be `None`, a list, or a callable')

        if (callable(default) or
                (isinstance(default, list) and len(default) > 0) or
                (not isinstance(default, list) and default is not None)) and \
            (callable(related_default) or
                (isinstance(related_default, list) and len(related_default) > 0) or
                (not isinstance(related_default, list) and related_default is not None)):
            raise ValueError('Default and `related_default` cannot both be used')

        if not verbose_related_name:
            verbose_related_name = sentencecase(related_name)

        super(RelatedAttribute, self).__init__(
            init_value=init_value, default=default, default_cleaned_value=default_cleaned_value,
            none_value=none_value, verbose_name=verbose_name, description=description,
            primary=False, unique=False, unique_case_insensitive=False)
        self.primary_class = None
        self.related_class = related_class
        self.related_name = related_name
        self.verbose_related_name = verbose_related_name
        self.related_init_value = related_init_value
        self.related_default = related_default
        self.min_related = min_related
        self.max_related = max_related
        self.min_related_rev = min_related_rev
        self.max_related_rev = max_related_rev

    def get_related_init_value(self, obj):
        """ Get initial related value for attribute

        Args:
            obj (:obj:`object`): object whose attribute is being initialized

        Returns:
            value (:obj:`object`): initial value

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        return copy.copy(self.related_init_value)

    def get_related_default(self, obj):
        """ Get default related value for attribute

        Args:
            obj (:obj:`Model`): object whose attribute is being initialized

        Returns:
            :obj:`object`: initial value

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        if self.related_default and callable(self.related_default):
            return self.related_default()

        return copy.copy(self.related_default)

    @abc.abstractmethod
    def set_related_value(self, obj, new_values):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_values (:obj:`object`): value of the attribute

        Returns:
            :obj:`object`: value of the attribute
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def related_validate(self, obj, value):
        """ Determine if `value` is a valid value of the related attribute

        Args:
            obj (:obj:`Model`): object to validate
            value (:obj:`list`): value to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        pass  # pragma: no cover

    def serialize(self, value, encoded=None):
        """ Serialize related object

        Args:
            value (:obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        pass  # pragma: no cover

    def deserialize(self, value, objects, decoded=None):
        """ Deserialize value

        Args:
            values (:obj:`object`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        pass  # pragma: no cover

    def to_builtin(self, value):
        """ Encode a value of the attribute using a simple Python representation (dict, list, str, float, bool, None)
        that is compatible with JSON and YAML

        Args:
            value (:obj:`object`): value of the attribute

        Returns:
            :obj:`object`: simple Python representation of a value of the attribute
        """
        raise Exception('This function should not be executed')

    def from_builtin(self, json):
        """ Decode a simple Python representation (dict, list, str, float, bool, None) of a value of the attribute
        that is compatible with JSON and YAML

        Args:
            json (:obj:`object`): simple Python representation of a value of the attribute

        Returns:
            :obj:`object`: decoded value of the attribute
        """
        raise Exception('This function should not be executed')

    def _get_tabular_schema_format(self):
        """ Generate a string which represents the format of the attribute for use
        in tabular-formatted schemas

        Returns:
            :obj:`str`: string which represents the format of the attribute for use
                in tabular-formatted schemas
        """
        return "{}('{}', related_name='{}')".format(self.__class__.__name__.rpartition('Attribute')[0],
                                                    self.related_class.__name__, self.related_name)


class OneToOneAttribute(RelatedAttribute):
    """ Represents a one-to-one relationship between two types of objects. """

    def __init__(self, related_class, related_name='',
                 default=None, default_cleaned_value=None, related_default=None, none_value=None,
                 min_related=0, min_related_rev=0,
                 verbose_name='', verbose_related_name='', description=''):
        """
        Args:
            related_class (:obj:`class`): related class
            related_name (:obj:`str`, optional): name of related attribute on `related_class`
            default (:obj:`callable`, optional): callable which returns default value
            default_cleaned_value (:obj:`callable`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            related_default (:obj:`callable`, optional): callable which returns default related value
            none_value (:obj:`object`, optional): none value
            min_related (:obj:`int`, optional): minimum number of related objects in the forward direction
            min_related_rev (:obj:`int`, optional): minimum number of related objects in the reverse direction
            verbose_name (:obj:`str`, optional): verbose name
            verbose_related_name (:obj:`str`, optional): verbose related name
            description (:obj:`str`, optional): description
        """
        super(OneToOneAttribute, self).__init__(related_class, related_name=related_name,
                                                init_value=None, default=default,
                                                default_cleaned_value=default_cleaned_value,
                                                related_init_value=None, related_default=related_default,
                                                none_value=none_value,
                                                min_related=min_related, max_related=1,
                                                min_related_rev=min_related_rev, max_related_rev=1,
                                                verbose_name=verbose_name, description=description,
                                                verbose_related_name=verbose_related_name)
        if min_related:
            self.type = Model
        else:
            self.type = (Model, None.__class__)

        if min_related_rev:
            self.related_type = Model
        else:
            self.related_type = (Model, None.__class__)

    def set_value(self, obj, new_value):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_value (:obj:`Model`): new attribute value

        Returns:
            :obj:`Model`: new attribute value

        Raises:
            :obj:`ValueError`: if related attribute of `new_value` is not `None`
        """
        cur_value = getattr(obj, self.name)
        if cur_value is new_value:
            return new_value

        if new_value and getattr(new_value, self.related_name):
            old_related = getattr(new_value, self.related_name)
            old_related_cls = old_related.__class__
            new_cls = new_value.__class__
            raise ValueError(("Attribute '{}:{}' of '{}:{}' cannot be set because it is not `None`. "
                              "The values of one-to-one attributes cannot be directly changed to other non-`None` values because "
                              "this would opaquely change the reverse relationship of the related object. "
                              "To change the value of this attribute to another non-`None` value, first set the value of the attribute "
                              "to `None`."
                              ).format(
                old_related_cls.__name__, old_related.serialize(),
                new_cls.__name__, new_value.serialize()))

        if self.related_name:
            if cur_value:
                cur_value.__setattr__(self.related_name, None, propagate=False)

            if new_value:
                new_value.__setattr__(self.related_name, obj, propagate=False)

        return new_value

    def set_related_value(self, obj, new_value):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_value (:obj:`Model`): value of the attribute

        Returns:
            :obj:`Model`: value of the attribute

        Raises:
            :obj:`ValueError`: if related property is not defined or the attribute of `new_value` is not `None`
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        cur_value = getattr(obj, self.related_name)
        if cur_value is new_value:
            return new_value
        if cur_value and new_value is not None:
            raise ValueError(("Attribute '{}:{}' of '{}:{}' cannot be set because it is not `None`. "
                              "The values of one-to-one attributes cannot be directly changed to other non-`None` values because "
                              "this would opaquely change the reverse relationship of the related object. "
                              "To change the value of this attribute to another non-`None` value, first set the value of the attribute "
                              "to `None`."
                              ).format(
                self.related_name, cur_value.serialize(),
                obj.__class__.__name__, obj.serialize()))

        if new_value and getattr(new_value, self.name):
            raise ValueError(("Attribute '{}:{}' of '{}:{}' cannot be set because it is not `None`. "
                              "The values of one-to-one attributes cannot be directly changed to other non-`None` values because "
                              "this would opaquely change the reverse relationship of the related object. "
                              "To change the value of this attribute to another non-`None` value, first set the value of the attribute "
                              "to `None`."
                              ).format(
                self.name, getattr(new_value, self.name).serialize(),
                new_value.__class__.__name__, new_value.serialize()))

        if cur_value:
            cur_value.__setattr__(self.name, None, propagate=False)

        if new_value:
            new_value.__setattr__(self.name, obj, propagate=False)

        return new_value

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`Model`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if self.min_related == 1:
                errors.append('Value cannot be `None`')
        elif not isinstance(value, self.related_class):
            errors.append('Value must be an instance of "{:s}" or `None`'.format(
                self.related_class.__name__))
        elif self.related_name:
            if obj is not getattr(value, self.related_name):
                errors.append('Object must be related value')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def related_validate(self, obj, value):
        """ Determine if `value` is a valid value of the related attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`list` of :obj:`Model`): value to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if self.min_related_rev == 1:
                errors.append('Value cannot be `None`')
        elif value and self.related_name:
            if not isinstance(value, self.primary_class):
                errors.append('Related value must be an instance of "{:s}" not "{}"'.format(
                    self.primary_class.__name__, value.__class__.__name__))
            elif getattr(value, self.name) is not obj:
                errors.append('Object must be related value')

        if errors:
            return InvalidAttribute(self, errors, related=True)
        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`Model`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`Model`: copy of value
        """
        if value is None:
            return None
        else:
            return objects_and_copies[value]

    def serialize(self, value, encoded=None):
        """ Serialize related object

        Args:
            value (:obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        if self.related_class.Meta.table_format == TableFormat.cell:
            return json.dumps(value.to_dict(value, encode_primary_objects=False, encoded=encoded),
                              indent=8)

        else:
            if value is None:
                return ''

            primary_attr = value.__class__.Meta.primary_attribute
            return primary_attr.serialize(getattr(value, primary_attr.name))

    def deserialize(self, value, objects, decoded=None):
        """ Deserialize value

        Args:
            value (:obj:`str`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if not value:
            return (None, None)

        if self.related_class.Meta.table_format == TableFormat.cell:
            try:
                obj = self.related_class.from_dict(json.loads(value), [self.related_class], decode_primary_objects=False,
                                                   primary_objects=objects, decoded=decoded)
                error = None
            except Exception as exception:
                obj = None
                error = InvalidAttribute(self, ['{}: {}'.format(exception.__class__.__name__, str(exception))])
            return (obj, error)

        else:
            related_objs = set()
            related_classes = chain([self.related_class],
                                    get_subclasses(self.related_class))
            for related_class in related_classes:
                if issubclass(related_class, Model) and related_class in objects and value in objects[related_class]:
                    related_objs.add(objects[related_class][value])

            if len(related_objs) == 0:
                primary_attr = self.related_class.Meta.primary_attribute
                return (None, InvalidAttribute(self, ['Unable to find {} with {}={}'.format(
                    self.related_class.__name__, primary_attr.name, quote(value))]))

            if len(related_objs) == 1:
                return (related_objs.pop(), None)

            return (None, InvalidAttribute(self, ['Multiple matching objects with primary attribute = {}'.format(value)]))

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        right_child = getattr(right, self.name)
        if not right_child:
            return

        cur_left_child = getattr(left, self.name)
        new_left_child = right_objs_in_left.get(right_child, right_child)

        new_left_child_parent = getattr(new_left_child, self.related_name)

        if new_left_child != cur_left_child and \
                ((left == right and new_left_child_parent) or (left != right and cur_left_child)):
            raise ValueError('Cannot join "{}" {} and {} of {} "{}" and "{}"'.format(
                self.related_name,
                left,
                new_left_child_parent,
                self.related_class.__name__,
                cur_left_child,
                new_left_child))

        setattr(right, self.name, None)
        setattr(left, self.name, new_left_child)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        sheet_models = sheet_models or []
        validation = super(OneToOneAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        if self.related_class in sheet_models:
            if self.related_class.Meta.primary_attribute:
                validation.type = wc_utils.workbook.io.FieldValidationType.list

            related_has_doc_heading = self.related_class == doc_metadata_model
            related_has_multiple_cells = False
            for attr_name in self.related_class.Meta.attribute_order:
                attr = self.related_class.Meta.attributes[attr_name]
                if isinstance(attr, RelatedAttribute) and attr.related_class.Meta.table_format == TableFormat.multiple_cells:
                    related_has_multiple_cells = True
                    break

            if self.related_class.Meta.table_format == TableFormat.row:
                related_ws = self.related_class.Meta.verbose_name_plural
                if self.related_class.Meta.primary_attribute:
                    related_col = get_column_letter(self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1)
                    source = '!!{}:{}'.format(related_ws, related_col)
                    start_row = 3 + related_has_doc_heading + related_has_multiple_cells
                    validation.allowed_list_values = "='!!{}'!${}${}:${}${}".format(related_ws, related_col, start_row, related_col, 2**20)
                else:
                    source = related_ws
            else:
                related_ws = self.related_class.Meta.verbose_name
                if self.related_class.Meta.primary_attribute:
                    related_row = self.related_class.get_attr_index(
                        self.related_class.Meta.primary_attribute) + 2 + related_has_doc_heading
                    source = '!!{}:{}'.format(related_ws, related_row)
                    start_col = get_column_letter(2 + related_has_multiple_cells)
                    validation.allowed_list_values = "='!!{}'!${}${}:${}${}".format(related_ws, start_col, related_row, 'XFD', related_row)
                else:
                    source = related_ws

            validation.ignore_blank = self.min_related == 0
            if self.min_related == 0:
                input_message = ['Select a value from "{}" or blank.'.format(source)]
                error_message = ['Value must be a value from "{}" or blank.'.format(source)]
            else:
                input_message = ['Select a value from "{}".'.format(source)]
                error_message = ['Value must be a value from "{}".'.format(source)]
        else:
            if self.min_related == 0:
                validation.type = wc_utils.workbook.io.FieldValidationType.any
                validation.ignore_blank = True
                input_message = ['Enter a string or blank.']
                error_message = ['Value must be a string or blank.']
            else:
                validation.type = wc_utils.workbook.io.FieldValidationType.length
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
                validation.allowed_scalar_value = 1
                validation.ignore_blank = False
                input_message = ['Enter a string.']
                error_message = ['Value must be a string.']

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: {}.'.format(default.serialize()))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class ManyToOneAttribute(RelatedAttribute):
    """ Represents a many-to-one relationship between two types of objects.
    This is analagous to a foreign key relationship in a database.

    Attributes:
        related_manager (:obj:`type`): related manager
    """

    def __init__(self, related_class, related_name='',
                 default=None, default_cleaned_value=None, related_default=list(), none_value=None,
                 min_related=0, min_related_rev=0, max_related_rev=float('inf'),
                 verbose_name='', verbose_related_name='', description='',
                 related_manager=ManyToOneRelatedManager):
        """
        Args:
            related_class (:obj:`class`): related class
            related_name (:obj:`str`, optional): name of related attribute on `related_class`
            default (:obj:`callable`, optional): callable which returns the default value
            default_cleaned_value (:obj:`callable`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            related_default (:obj:`callable`, optional): callable which returns the default related value
            none_value (:obj:`object`, optional): none value
            min_related (:obj:`int`, optional): minimum number of related objects in the forward direction
            min_related_rev (:obj:`int`, optional): minimum number of related objects in the reverse direction
            max_related_rev (:obj:`int`, optional): maximum number of related objects in the reverse direction
            verbose_name (:obj:`str`, optional): verbose name
            verbose_related_name (:obj:`str`, optional): verbose related name
            description (:obj:`str`, optional): description
            related_manager (:obj:`type`, optional): related manager
        """
        super(ManyToOneAttribute, self).__init__(
            related_class, related_name=related_name,
            init_value=None, default=default, default_cleaned_value=default_cleaned_value,
            related_init_value=related_manager, related_default=related_default, none_value=none_value,
            min_related=min_related, max_related=1, min_related_rev=min_related_rev, max_related_rev=max_related_rev,
            verbose_name=verbose_name, description=description, verbose_related_name=verbose_related_name)
        if min_related:
            self.type = Model
        else:
            self.type = (Model, None.__class__)
        self.related_type = RelatedManager
        self.related_manager = related_manager

    def get_related_init_value(self, obj):
        """ Get initial related value for attribute

        Args:
            obj (:obj:`object`): object whose attribute is being initialized

        Returns:
            value (:obj:`object`): initial value

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        return self.related_manager(obj, self)

    def set_value(self, obj, new_value):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_value (:obj:`Model`): new attribute value

        Returns:
            :obj:`Model`: new attribute value
        """
        cur_value = getattr(obj, self.name)
        if cur_value is new_value:
            return new_value

        if self.related_name:
            if cur_value:
                cur_related = getattr(cur_value, self.related_name)
                cur_related.remove(obj, propagate=False)

            if new_value:
                new_related = getattr(new_value, self.related_name)
                new_related.append(obj, propagate=False)

        return new_value

    def set_related_value(self, obj, new_values):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_values (:obj:`list`): value of the attribute

        Returns:
            :obj:`list`: value of the attribute

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        new_values_copy = list(new_values)

        cur_values = getattr(obj, self.related_name)
        cur_values.clear()
        cur_values.extend(new_values_copy)

        return cur_values

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`Model`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if value is None:
            if self.min_related == 1:
                errors.append('Value cannot be `None`')
        elif not isinstance(value, self.related_class):
            errors.append('Value must be an instance of "{:s}" or `None`'.format(
                self.related_class.__name__))
        elif self.related_name:
            related_value = getattr(value, self.related_name)
            if not isinstance(related_value, self.related_manager):
                errors.append('Related value must be a `{}`'.format(self.related_manager.__name__)
                              )  # pragma: no cover # unreachable due to above error checking
            if obj not in related_value:
                errors.append('Object must be in related values')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def related_validate(self, obj, value):
        """ Determine if `value` is a valid value of the related attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`list` of :obj:`Model`): value to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if self.related_name:
            if not isinstance(value, list):
                errors.append('Related value must be a list')
            elif len(value) < self.min_related_rev:
                errors.append('There must be at least {} related values'.format(
                    self.min_related_rev))
            elif len(value) > self.max_related_rev:
                errors.append('There cannot be more than {} related values'.format(
                    self.max_related_rev))
            else:
                for v in value:
                    if not isinstance(v, self.primary_class):
                        errors.append('Related value must be an instance of "{:s}" not "{}"'.format(
                            self.primary_class.__name__, v.__class__.__name__))
                    elif getattr(v, self.name) is not obj:
                        errors.append('Object must be related value')

        if errors:
            return InvalidAttribute(self, errors, related=True)
        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`Model`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`Model`: copy of value
        """
        if value is None:
            return None
        else:
            return objects_and_copies[value]

    def serialize(self, value, encoded=None):
        """ Serialize related object

        Args:
            value (:obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        if self.related_class.Meta.table_format == TableFormat.cell:
            return json.dumps(value.to_dict(value, encode_primary_objects=False, encoded=encoded),
                              indent=8)

        else:
            if value is None:
                return ''

            primary_attr = value.__class__.Meta.primary_attribute
            return primary_attr.serialize(getattr(value, primary_attr.name))

    def deserialize(self, value, objects, decoded=None):
        """ Deserialize value

        Args:
            value (:obj:`str`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if not value:
            return (None, None)

        if self.related_class.Meta.table_format == TableFormat.cell:
            try:
                obj = self.related_class.from_dict(json.loads(value), [self.related_class], decode_primary_objects=False,
                                                   primary_objects=objects, decoded=decoded)
                error = None
            except Exception as exception:
                obj = None
                error = InvalidAttribute(self, ['{}: {}'.format(exception.__class__.__name__, str(exception))])
            return (obj, error)

        else:
            related_objs = set()
            related_classes = chain([self.related_class],
                                    get_subclasses(self.related_class))
            for related_class in related_classes:
                if issubclass(related_class, Model) and related_class in objects and value in objects[related_class]:
                    related_objs.add(objects[related_class][value])

            if len(related_objs) == 0:
                primary_attr = self.related_class.Meta.primary_attribute
                return (None, InvalidAttribute(self, ['Unable to find {} with {}={}'.format(
                    self.related_class.__name__, primary_attr.name, quote(value))]))

            if len(related_objs) == 1:
                return (related_objs.pop(), None)

            return (None, InvalidAttribute(self, ['Multiple matching objects with primary attribute = {}'.format(value)]))

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        right_child = getattr(right, self.name)
        if not right_child:
            return

        cur_left_child = getattr(left, self.name)
        new_left_child = right_objs_in_left.get(right_child, right_child)

        if left != right and cur_left_child and new_left_child and cur_left_child != new_left_child:
            raise ValueError('Cannot join {} and {} of {}.{}'.format(
                cur_left_child,
                new_left_child,
                left.__class__.__name__,
                self.name))
        setattr(right, self.name, None)
        setattr(left, self.name, new_left_child)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        sheet_models = sheet_models or []
        validation = super(ManyToOneAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        if self.related_class in sheet_models:
            if self.related_class.Meta.primary_attribute:
                validation.type = wc_utils.workbook.io.FieldValidationType.list

            related_has_doc_heading = self.related_class == doc_metadata_model
            related_has_multiple_cells = False
            for attr_name in self.related_class.Meta.attribute_order:
                attr = self.related_class.Meta.attributes[attr_name]
                if isinstance(attr, RelatedAttribute) and attr.related_class.Meta.table_format == TableFormat.multiple_cells:
                    related_has_multiple_cells = True
                    break

            if self.related_class.Meta.table_format == TableFormat.row:
                related_ws = self.related_class.Meta.verbose_name_plural
                if self.related_class.Meta.primary_attribute:
                    related_col = get_column_letter(self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1)
                    source = '!!{}:{}'.format(related_ws, related_col)
                    start_row = 3 + related_has_doc_heading + related_has_multiple_cells
                    validation.allowed_list_values = "='!!{}'!${}${}:${}${}".format(related_ws, related_col, start_row, related_col, 2**20)
                else:
                    source = related_ws
            else:
                related_ws = self.related_class.Meta.verbose_name
                if self.related_class.Meta.primary_attribute:
                    related_row = self.related_class.get_attr_index(
                        self.related_class.Meta.primary_attribute) + 2 + related_has_doc_heading
                    source = '!!{}:{}'.format(related_ws, related_row)
                    start_col = get_column_letter(2 + related_has_multiple_cells)
                    validation.allowed_list_values = "='!!{}'!${}${}:${}${}".format(related_ws, start_col, related_row, 'XFD', related_row)
                else:
                    source = related_ws

            validation.ignore_blank = self.min_related == 0
            if self.min_related == 0:
                input_message = ['Select a value from "{}" or blank.'.format(source)]
                error_message = ['Value must be a value from "{}" or blank.'.format(source)]
            else:
                input_message = ['Select a value from "{}".'.format(source)]
                error_message = ['Value must be a value from "{}".'.format(source)]
        else:
            if self.min_related == 0:
                validation.type = wc_utils.workbook.io.FieldValidationType.any
                validation.ignore_blank = True
                input_message = ['Enter a string or blank.']
                error_message = ['Value must be a string or blank.']
            else:
                validation.type = wc_utils.workbook.io.FieldValidationType.length
                validation.criterion = wc_utils.workbook.io.FieldValidationCriterion['>=']
                validation.allowed_scalar_value = 1
                validation.ignore_blank = False
                input_message = ['Enter a string.']
                error_message = ['Value must be a string.']

        default = self.get_default_cleaned_value()
        if default is not None:
            input_message.append('Default: {}.'.format(default.serialize()))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class OneToManyAttribute(RelatedAttribute):
    """ Represents a one-to-many relationship between two types of objects.
    This is analagous to a foreign key relationship in a database.

    Attributes:
        related_manager (:obj:`type`): related manager
    """

    def __init__(self, related_class, related_name='', default=list(), default_cleaned_value=list(),
                 related_default=None, none_value=list,
                 min_related=0, max_related=float('inf'), min_related_rev=0,
                 verbose_name='', verbose_related_name='', description='',
                 related_manager=OneToManyRelatedManager):
        """
        Args:
            related_class (:obj:`class`): related class
            related_name (:obj:`str`, optional): name of related attribute on `related_class`
            default (:obj:`callable`, optional): function which returns the default value
            default_cleaned_value (:obj:`callable`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            related_default (:obj:`callable`, optional): function which returns the default related value
            none_value (:obj:`object`, optional): none value
            min_related (:obj:`int`, optional): minimum number of related objects in the forward direction
            max_related (:obj:`int`, optional): maximum number of related objects in the forward direction
            min_related_rev (:obj:`int`, optional): minimum number of related objects in the reverse direction
            verbose_name (:obj:`str`, optional): verbose name
            verbose_related_name (:obj:`str`, optional): verbose related name
            description (:obj:`str`, optional): description
            related_manager (:obj:`type`, optional): related manager
        """
        super(OneToManyAttribute, self).__init__(
            related_class, related_name=related_name,
            init_value=related_manager, default=default, default_cleaned_value=default_cleaned_value,
            related_init_value=None, related_default=related_default, none_value=none_value,
            min_related=min_related, max_related=max_related, min_related_rev=min_related_rev, max_related_rev=1,
            verbose_name=verbose_name, description=description, verbose_related_name=verbose_related_name)
        self.type = RelatedManager
        if min_related_rev:
            self.related_type = Model
        else:
            self.related_type = (Model, None.__class__)
        self.related_manager = related_manager

    def get_init_value(self, obj):
        """ Get initial value for attribute

        Args:
            obj (:obj:`Model`): object whose attribute is being initialized

        Returns:
            :obj:`object`: initial value
        """
        return self.related_manager(obj, self)

    def set_value(self, obj, new_values):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_values (:obj:`list`): value of the attribute

        Returns:
            :obj:`list`: value of the attribute
        """
        new_values_copy = list(new_values)

        cur_values = getattr(obj, self.name)
        cur_values.clear()
        cur_values.extend(new_values_copy)

        return cur_values

    def set_related_value(self, obj, new_value):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_value (:obj:`Model`): new attribute value

        Returns:
            :obj:`Model`: new attribute value

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        cur_value = getattr(obj, self.related_name)
        if cur_value is new_value:
            return new_value

        if cur_value:
            cur_related = getattr(cur_value, self.name)
            cur_related.remove(obj, propagate=False)

        if new_value:
            new_related = getattr(new_value, self.name)
            new_related.append(obj, propagate=False)

        return new_value

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`list` of :obj:`Model`): value to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if not isinstance(value, list):
            errors.append('Related value must be a list')
        elif len(value) < self.min_related:
            errors.append(
                'There must be at least {} related values'.format(self.min_related))
        elif len(value) > self.max_related:
            errors.append(
                'There must be no more than {} related values'.format(self.max_related))
        else:
            for v in value:
                if not isinstance(v, self.related_class):
                    errors.append('Value must be an instance of "{:s}"'.format(
                        self.related_class.__name__))
                elif self.related_name and getattr(v, self.related_name) is not obj:
                    errors.append('Object must be related value')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def related_validate(self, obj, value):
        """ Determine if `value` is a valid value of the related attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`Model`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if self.related_name:
            if value is None:
                if self.min_related_rev == 1:
                    errors.append('Value cannot be `None`')
            elif not isinstance(value, self.primary_class):
                errors.append('Value must be an instance of "{:s}" or `None`'.format(
                    self.primary_class.__name__))
            else:
                related_value = getattr(value, self.name)
                if not isinstance(related_value, self.related_manager):
                    errors.append('Related value must be a `{}`'.format(self.related_manager.__name__)
                                  )  # pragma: no cover # unreachable due to above error checking
                if obj not in related_value:
                    errors.append('Object must be in related values')

        if errors:
            return InvalidAttribute(self, errors, related=True)
        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`list` of :obj:`Model`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`list` of :obj:`Model`: copy of value
        """
        copy_value = []
        for v in value:
            copy_value.append(objects_and_copies[v])
        return copy_value

    def serialize(self, value, encoded=None):
        """ Serialize related object

        Args:
            value (:obj:`list` of :obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        if self.related_class.Meta.table_format == TableFormat.cell:
            return json.dumps([v.to_dict(v, encode_primary_objects=False, encoded=encoded) for v in value],
                              indent=8)

        else:
            serialized_vals = []
            for v in value:
                primary_attr = v.__class__.Meta.primary_attribute
                serialized_vals.append(primary_attr.serialize(
                    getattr(v, primary_attr.name)))

            serialized_vals.sort(key=natsort_keygen(alg=ns.IGNORECASE))
            return ', '.join(serialized_vals)

    def deserialize(self, values, objects, decoded=None):
        """ Deserialize value

        Args:
            values (:obj:`object`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if not values:
            return (list(), None)

        if self.related_class.Meta.table_format == TableFormat.cell:
            try:
                objs = []
                for v in json.loads(values):
                    objs.append(self.related_class.from_dict(v, [self.related_class], decode_primary_objects=False,
                                                             primary_objects=objects, decoded=decoded))
                error = None
            except Exception as exception:
                objs = None
                error = InvalidAttribute(self, ['{}: {}'.format(exception.__class__.__name__, str(exception))])
            return (objs, error)

        else:
            deserialized_values = list()
            errors = []
            for value in values.split(','):
                value = value.strip()

                related_objs = set()
                related_classes = chain(
                    [self.related_class], get_subclasses(self.related_class))
                for related_class in related_classes:
                    if issubclass(related_class, Model) and related_class in objects and value in objects[related_class]:
                        related_objs.add(objects[related_class][value])

                if len(related_objs) == 1:
                    deserialized_values.append(related_objs.pop())
                elif len(related_objs) == 0:
                    errors.append('Unable to find {} with {}={}'.format(
                        self.related_class.__name__, self.related_class.Meta.primary_attribute.name, quote(value)))
                else:
                    errors.append(
                        'Multiple matching objects with primary attribute = {}'.format(value))

            if errors:
                return (None, InvalidAttribute(self, errors))
            return (deserialized_values, None)

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        left_children = getattr(left, self.name)
        right_children = getattr(right, self.name)

        for right_child in list(right_children):
            left_child = right_objs_in_left.get(right_child, right_child)
            cur_left_child_parent = getattr(left_child, self.related_name)

            if left_child != right_child and cur_left_child_parent and cur_left_child_parent != left:
                raise ValueError('Cannot join {} and {} of {}.{}'.format(
                    left,
                    cur_left_child_parent,
                    left_child.__class__.__name__,
                    self.related_name))

            right_children.remove(right_child)
            left_children.append(left_child)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        sheet_models = sheet_models or []
        validation = super(OneToManyAttribute, self).get_excel_validation(sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        if self.related_class in sheet_models:
            if self.related_class.Meta.table_format == TableFormat.row:
                related_ws = self.related_class.Meta.verbose_name_plural
                if self.related_class.Meta.primary_attribute:
                    related_col = get_column_letter(self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1)
                    source = ' from "{}:{}"'.format(related_ws, related_col)
                else:
                    source = ' from "{}"'.format(related_ws)
            else:
                related_ws = self.related_class.Meta.verbose_name
                if self.related_class.Meta.primary_attribute:
                    related_row = self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1
                    source = ' from "{}:{}"'.format(related_ws, related_row)
                else:
                    source = ' from "{}"'.format(related_ws)
        else:
            source = ''

        validation.ignore_blank = self.min_related == 0
        if self.min_related == 0:
            input_message = ['Enter a comma-separated list of values{} or blank.'.format(source)]
            error_message = ['Value must be a comma-separated list of values{} or blank.'.format(source)]
        else:
            input_message = ['Enter a comma-separated list of values{}.'.format(source)]
            error_message = ['Value must be a comma-separated list of values{}.'.format(source)]

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: {}.'.format(', '.join([v.serialize() for v in default])))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class ManyToManyAttribute(RelatedAttribute):
    """ Represents a many-to-many relationship between two types of objects.

    Attributes:
        related_manager (:obj:`type`): related manager
    """

    def __init__(self, related_class, related_name='', default=list(), default_cleaned_value=list(),
                 related_default=list(), none_value=list,
                 min_related=0, max_related=float('inf'), min_related_rev=0, max_related_rev=float('inf'),
                 verbose_name='', verbose_related_name='', description='',
                 related_manager=ManyToManyRelatedManager):
        """
        Args:
            related_class (:obj:`class`): related class
            related_name (:obj:`str`, optional): name of related attribute on `related_class`
            default (:obj:`callable`, optional): function which returns the default values
            default_cleaned_value (:obj:`callable`, optional): value to replace
                :obj:`None` values with during cleaning, or function
                which computes the value to replace :obj:`None` values
            related_default (:obj:`callable`, optional): function which returns the default related values
            none_value (:obj:`object`, optional): none value
            min_related (:obj:`int`, optional): minimum number of related objects in the forward direction
            max_related (:obj:`int`, optional): maximum number of related objects in the forward direction
            min_related_rev (:obj:`int`, optional): minimum number of related objects in the reverse direction
            max_related_rev (:obj:`int`, optional): maximum number of related objects in the reverse direction
            verbose_name (:obj:`str`, optional): verbose name
            verbose_related_name (:obj:`str`, optional): verbose related name
            description (:obj:`str`, optional): description
            related_manager (:obj:`type`, optional): related manager
        """
        super(ManyToManyAttribute, self).__init__(
            related_class, related_name=related_name,
            init_value=related_manager, default=default, default_cleaned_value=default_cleaned_value,
            related_init_value=related_manager, related_default=related_default, none_value=none_value,
            min_related=min_related, max_related=max_related, min_related_rev=min_related_rev, max_related_rev=max_related_rev,
            verbose_name=verbose_name, description=description, verbose_related_name=verbose_related_name)
        self.type = RelatedManager
        self.related_type = RelatedManager
        self.related_manager = related_manager

    def get_init_value(self, obj):
        """ Get initial value for attribute

        Args:
            obj (:obj:`Model`): object whose attribute is being initialized

        Returns:
            :obj:`object`: initial value
        """
        return self.related_manager(obj, self, related=False)

    def get_related_init_value(self, obj):
        """ Get initial related value for attribute

        Args:
            obj (:obj:`object`): object whose attribute is being initialized

        Returns:
            value (:obj:`object`): initial value

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')
        return self.related_manager(obj, self, related=True)

    def set_value(self, obj, new_values):
        """ Get value of attribute of object

        Args:
            obj (:obj:`Model`): object
            new_values (:obj:`list`): new attribute value

        Returns:
            :obj:`list`: new attribute value
        """
        new_values_copy = list(new_values)

        cur_values = getattr(obj, self.name)
        cur_values.clear()
        cur_values.extend(new_values_copy)

        return cur_values

    def set_related_value(self, obj, new_values):
        """ Update the values of the related attributes of the attribute

        Args:
            obj (:obj:`object`): object whose attribute should be set
            new_values (:obj:`list`): value of the attribute

        Returns:
            :obj:`list`: value of the attribute

        Raises:
            :obj:`ValueError`: if related property is not defined
        """
        if not self.related_name:
            raise ValueError('Related property is not defined')

        new_values_copy = list(new_values)

        cur_values = getattr(obj, self.related_name)
        cur_values.clear()
        cur_values.extend(new_values_copy)

        return cur_values

    def validate(self, obj, value):
        """ Determine if `value` is a valid value of the attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`list` of :obj:`Model`): value of attribute to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if not isinstance(value, list):
            errors.append('Value must be a `list`')
        elif len(value) < self.min_related:
            errors.append(
                'There must be at least {} related values'.format(self.min_related))
        elif len(value) > self.max_related:
            errors.append(
                'There cannot be more than {} related values'.format(self.max_related))
        else:
            for v in value:
                if not isinstance(v, self.related_class):
                    errors.append('Value must be a `list` of "{:s}"'.format(
                        self.related_class.__name__))

                elif self.related_name:
                    related_v = getattr(v, self.related_name)
                    if not isinstance(related_v, self.related_manager):
                        errors.append(
                            'Related value must be a `{}`'.format(self.related_manager.__name__)
                        )  # pragma: no cover # unreachable due to above error checking
                    if obj not in related_v:
                        errors.append('Object must be in related values')

        if errors:
            return InvalidAttribute(self, errors)
        return None

    def related_validate(self, obj, value):
        """ Determine if `value` is a valid value of the related attribute

        Args:
            obj (:obj:`Model`): object being validated
            value (:obj:`list` of :obj:`Model`): value to validate

        Returns:
            :obj:`InvalidAttribute` or None: None if attribute is valid, other return list of errors as an instance of `InvalidAttribute`
        """
        errors = []

        if self.related_name:
            if not isinstance(value, list):
                errors.append('Related value must be a list')
            elif len(value) < self.min_related_rev:
                errors.append('There must be at least {} related values'.format(
                    self.min_related_rev))
            elif len(value) > self.max_related_rev:
                errors.append('There cannot be more than {} related values'.format(
                    self.max_related_rev))
            else:
                for v in value:
                    if not isinstance(v, self.primary_class):
                        errors.append('Related value must be an instance of "{:s}" not "{}"'.format(
                            self.primary_class.__name__, v.__class__.__name__))
                    elif obj not in getattr(v, self.name):
                        errors.append('Object must be in related values')

        if errors:
            return InvalidAttribute(self, errors, related=True)
        return None

    def copy_value(self, value, objects_and_copies):
        """ Copy value

        Args:
            value (:obj:`list` of :obj:`Model`): value
            objects_and_copies (:obj:`dict`): dictionary that maps objects to their copies

        Returns:
            :obj:`list` of :obj:`Model`: copy of value
        """
        copy_value = []
        for v in value:
            copy_value.append(objects_and_copies[v])
        return copy_value

    def serialize(self, value, encoded=None):
        """ Serialize related object

        Args:
            value (:obj:`list` of :obj:`Model`): Python representation
            encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

        Returns:
            :obj:`str`: simple Python representation
        """
        if self.related_class.Meta.table_format == TableFormat.cell:
            return json.dumps([v.to_dict(v, encode_primary_objects=False, encoded=encoded) for v in value],
                              indent=8)

        else:
            serialized_vals = []
            for v in value:
                primary_attr = v.__class__.Meta.primary_attribute
                serialized_vals.append(primary_attr.serialize(
                    getattr(v, primary_attr.name)))

            serialized_vals.sort(key=natsort_keygen(alg=ns.IGNORECASE))
            return ', '.join(serialized_vals)

    def deserialize(self, values, objects, decoded=None):
        """ Deserialize value

        Args:
            values (:obj:`object`): String representation
            objects (:obj:`dict`): dictionary of objects, grouped by model
            decoded (:obj:`dict`, optional): dictionary of objects that have already been decoded

        Returns:
            :obj:`tuple` of `object`, `InvalidAttribute` or `None`: tuple of cleaned value and cleaning error
        """
        if not values:
            return (list(), None)

        if self.related_class.Meta.table_format == TableFormat.cell:
            try:
                objs = []
                for v in json.loads(values):
                    objs.append(self.related_class.from_dict(v, [self.related_class], decode_primary_objects=False,
                                                             primary_objects=objects, decoded=decoded))
                error = None
            except Exception as exception:
                objs = None
                error = InvalidAttribute(self, ['{}: {}'.format(exception.__class__.__name__, str(exception))])
            return (objs, error)

        else:
            deserialized_values = list()
            errors = []
            for value in values.split(','):
                value = value.strip()

                related_objs = set()
                related_classes = chain(
                    [self.related_class], get_subclasses(self.related_class))
                for related_class in related_classes:
                    if issubclass(related_class, Model) and related_class in objects and value in objects[related_class]:
                        related_objs.add(objects[related_class][value])

                if len(related_objs) == 1:
                    deserialized_values.append(related_objs.pop())
                elif len(related_objs) == 0:
                    primary_attr = self.related_class.Meta.primary_attribute
                    errors.append('Unable to find {} with {}={}'.format(
                        self.related_class.__name__, primary_attr.name, quote(value)))
                else:
                    errors.append(
                        'Multiple matching objects with primary attribute = {}'.format(value))

            if errors:
                return (None, InvalidAttribute(self, errors))
            return (deserialized_values, None)

    def merge(self, left, right, right_objs_in_left, left_objs_in_right):
        """ Merge an attribute of elements of two models

        Args:
            left (:obj:`Model`): an element in a model to merge
            right (:obj:`Model`): an element in a second model to merge
            right_objs_in_left (:obj:`dict`): mapping from objects in right model to objects in left model
            left_objs_in_right (:obj:`dict`): mapping from objects in left model to objects in right model

        Raises:
            :obj:`ValueError`: if the attributes of the elements of the models are different
        """
        left_children = getattr(left, self.name)
        right_children = getattr(right, self.name)

        for right_child in list(right_children):
            left_child = right_objs_in_left.get(right_child, right_child)
            right_children.remove(right_child)
            left_children.append(left_child)

    def get_excel_validation(self, sheet_models=None, doc_metadata_model=None):
        """ Get Excel validation

        Args:
            sheet_models (:obj:`list` of :obj:`Model`, optional): models encoded as separate sheets
            doc_metadata_model (:obj:`type`): model whose worksheet contains the document metadata

        Returns:
            :obj:`wc_utils.workbook.io.FieldValidation`: validation
        """
        sheet_models = sheet_models or []
        validation = super(ManyToManyAttribute, self).get_excel_validation(
            sheet_models=sheet_models, doc_metadata_model=doc_metadata_model)

        if self.related_class in sheet_models:
            if self.related_class.Meta.table_format == TableFormat.row:
                related_ws = self.related_class.Meta.verbose_name_plural
                if self.related_class.Meta.primary_attribute:
                    related_col = get_column_letter(self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1)
                    source = ' from "{}:{}"'.format(related_ws, related_col)
                else:
                    source = ' from "{}"'.format(related_ws)
            else:
                related_ws = self.related_class.Meta.verbose_name
                if self.related_class.Meta.primary_attribute:
                    related_row = self.related_class.get_attr_index(self.related_class.Meta.primary_attribute) + 1
                    source = ' from "{}:{}"'.format(related_ws, related_row)
                else:
                    source = ' from "{}"'.format(related_ws)
        else:
            source = ''

        validation.ignore_blank = self.min_related == 0
        if self.min_related == 0:
            input_message = ['Enter a comma-separated list of values{} or blank.'.format(source)]
            error_message = ['Value must be a comma-separated list of values{} or blank.'.format(source)]
        else:
            input_message = ['Enter a comma-separated list of values{}.'.format(source)]
            error_message = ['Value must be a comma-separated list of values{}.'.format(source)]

        default = self.get_default_cleaned_value()
        if default:
            input_message.append('Default: {}.'.format(', '.join([v.serialize() for v in default])))

        if validation.input_message:
            validation.input_message += '\n\n'
        validation.input_message = validation.input_message or ''
        validation.input_message += '\n\n'.join(input_message)

        if validation.error_message:
            validation.error_message += '\n\n'
        validation.error_message = validation.error_message or ''
        validation.error_message += '\n\n'.join(error_message)

        return validation


class InvalidObjectSet(object):
    """ Represents a list of invalid objects and invalid models

    Attributes:
        invalid_objects (:obj:`list` of :obj:`InvalidObject`): list of invalid objects
        invalid_models (:obj:`list` of :obj:`InvalidModel`): list of invalid models
    """

    def __init__(self, invalid_objects, invalid_models):
        """
        Args:
            invalid_objects (:obj:`list` of :obj:`InvalidObject`): list of invalid objects
            invalid_models (:obj:`list` of :obj:`InvalidModel`): list of invalid models

        Raises:
            :obj:`ValueError`: `invalid_models` is not unique
        """
        all_invalid_models = set()
        models = [invalid_model.model for invalid_model in invalid_models]
        duplicate_invalid_models = set(mdl for mdl in models
                                       if mdl in all_invalid_models or all_invalid_models.add(mdl))
        if duplicate_invalid_models:
            raise ValueError("duplicate invalid models: {}".format(
                [mdl.__class__.__name__ for mdl in duplicate_invalid_models]))
        self.invalid_objects = invalid_objects or []
        self.invalid_models = invalid_models or []

    def get_object_errors_by_model(self):
        """ Get object errors grouped by model

        Returns:
            :obj:`dict` of `Model`: `list` of `InvalidObject`: dictionary of object errors, grouped by model
        """
        object_errors_by_model = collections.defaultdict(list)
        for obj in self.invalid_objects:
            object_errors_by_model[obj.object.__class__].append(obj)

        return object_errors_by_model

    def get_model_errors_by_model(self):
        """ Get model errors grouped by models

        Returns:
            :obj:`dict` of `Model`: `InvalidModel`: dictionary of model errors, grouped by model
        """
        return {invalid_model.model: invalid_model for invalid_model in self.invalid_models}

    def __str__(self):
        """ Get string representation of errors

        Returns:
            :obj:`str`: string representation of errors
        """

        obj_errs = self.get_object_errors_by_model()
        mdl_errs = self.get_model_errors_by_model()

        models = set(obj_errs.keys())
        models.update(set(mdl_errs.keys()))
        models = natsorted(models, attrgetter('__name__'), alg=ns.IGNORECASE)

        error_forest = []
        for model in models:
            error_forest.append('{}:'.format(model.__name__))

            if model in mdl_errs:
                error_forest.append([str(mdl_errs[model])])

            if model in obj_errs:
                errs = natsorted(obj_errs[
                                 model], key=lambda x: x.object.get_primary_attribute(), alg=ns.IGNORECASE)
                error_forest.append([str(obj_err) for obj_err in errs])

        return indent_forest(error_forest)


class InvalidModel(object):
    """ Represents an invalid model, such as a model with an attribute that fails to meet specified constraints

    Attributes:
        model (:obj:`class`): `Model` class
        attributes (:obj:`list` of :obj:`InvalidAttribute`): list of invalid attributes and their errors
    """

    def __init__(self, model, attributes):
        """
        Args:
            model (:obj:`class`): `Model` class
            attributes (:obj:`list` of :obj:`InvalidAttribute`): list of invalid attributes and their errors
        """
        self.model = model
        self.attributes = attributes

    def __str__(self):
        """ Get string representation of errors

        Returns:
            :obj:`str`: string representation of errors
        """
        attrs = natsorted(
            self.attributes, key=lambda x: x.attribute.name, alg=ns.IGNORECASE)
        return indent_forest(attrs)


class InvalidObject(object):
    """ Represents an invalid object and its errors

    Attributes:
        object (:obj:`object`): invalid object
        attributes (:obj:`list` of :obj:`InvalidAttribute`): list of invalid attributes and their errors
    """

    def __init__(self, object, attributes):
        """
        Args:
            object (:obj:`Model`): invalid object
            attributes (:obj:`list` of :obj:`InvalidAttribute`): list of invalid attributes and their errors
        """
        self.object = object
        self.attributes = attributes

    def __str__(self):
        """ Get string representation of errors

        Returns:
            :obj:`str`: string representation of errors
        """
        error_forest = [str(self.object.serialize()) + ':']
        for attr in natsorted(self.attributes, key=lambda x: x.attribute.name, alg=ns.IGNORECASE):
            error_forest.append([attr])
        return indent_forest(error_forest)


class InvalidAttribute(object):
    """ Represents an invalid attribute and its errors

    Attributes:
        attribute (:obj:`Attribute`): invalid attribute
        messages (:obj:`list` of :obj:`str`): list of error messages
        related (:obj:`bool`): indicates if error is about value or related value
        location (:obj:`str`, optional): a string representation of the attribute's location in an input file
        value (:obj:`str`, optional): invalid input value
    """

    def __init__(self, attribute, messages, related=False, location=None, value=None):
        """
        Args:
            attribute (:obj:`Attribute`): invalid attribute
            message (:obj:`list` of :obj:`str`): list of error messages
            related (:obj:`bool`, optional): indicates if error is about value or related value
            location (:obj:`str`, optional): a string representation of the attribute's location in an
                input file
            value (:obj:`str`, optional): invalid input value
        """
        self.attribute = attribute
        self.messages = messages
        self.related = related
        self.location = location
        self.value = value

    def set_location_and_value(self, location, value):
        """ Set the location and value of the attribute

        Args:
            location (:obj:`str`): a string representation of the attribute's location in an input file
            value (:obj:`str`): the invalid input value
        """
        self.location = location
        if value is None:
            self.value = ''
        else:
            self.value = value

    def __str__(self):
        """ Get string representation of errors

        Returns:
            :obj:`str`: string representation of errors
        """
        if self.related:
            name = "'{}':".format(self.attribute.related_name)
        else:
            name = "'{}':".format(self.attribute.name)

        if self.value is not None:
            name += "'{}'".format(self.value)

        forest = [name]
        if self.location:
            forest.append([self.location,
                           [msg.rstrip() for msg in self.messages]])

        else:
            forest.append([msg.rstrip() for msg in self.messages])

        return indent_forest(forest)


def get_models(module=None, inline=True):
    """ Get models

    Args:
        module (:obj:`module`, optional): module
        inline (:obj:`bool`, optional): if true, return inline models

    Returns:
        :obj:`list` of :obj:`class`: list of model classes
    """
    if module:
        models = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Model) and attr is not Model:
                models.append(attr)

    else:
        models = get_subclasses(Model)

    if not inline:
        for model in list(models):
            if model.Meta.table_format in [TableFormat.cell, TableFormat.multiple_cells]:
                models.remove(model)

    return models


def get_model(name, module=None):
    """ Get first `Model` with name `name`

    Args:
        name (:obj:`str`): name
        module (:obj:`Module`, optional): module

    Returns:
        :obj:`class`: model class
    """
    for model in get_subclasses(Model):
        if name == model.__module__ + '.' + model.__name__ or \
                module is not None and module.__name__ == model.__module__ and name == model.__name__:
            return model

    return None


class Validator(object):
    """ Engine to validate sets of objects """

    def run(self, objects, get_related=False):
        """ Validate a list of objects and return their errors

        Args:
            objects (:obj:`Model` or `list` of `Model`): object or list of objects
            get_related (:obj:`bool`, optional): if true, get all related objects

        Returns:
            :obj:`InvalidObjectSet` or `None`: list of invalid objects/models and their errors
        """
        if isinstance(objects, Model):
            objects = [objects]

        if get_related:
            objects = Model.get_all_related(objects)

        error = self.clean(objects)
        if error:
            return error
        return self.validate(objects)

    def clean(self, objects):
        """ Clean a list of objects and return their errors

        Args:
            object (:obj:`list` of :obj:`Model`): list of objects

        Returns:
            :obj:`InvalidObjectSet` or `None`: list of invalid objects/models and their errors
        """

        object_errors = []
        for obj in objects:
            error = obj.clean()
            if error:
                object_errors.append(error)

        if object_errors:
            return InvalidObjectSet(object_errors, [])

        return None

    def validate(self, objects):
        """ Validate a list of objects and return their errors

        Args:
            object (:obj:`list` of :obj:`Model`): list of Model instances

        Returns:
            :obj:`InvalidObjectSet` or `None`: list of invalid objects/models and their errors
        """

        # validate individual objects
        object_errors = []
        for obj in objects:
            error = obj.validate()
            if error:
                object_errors.append(error)

        # group objects by class
        objects_by_class = {}
        for obj in objects:
            for cls in obj.__class__.Meta.inheritance:
                if cls not in objects_by_class:
                    objects_by_class[cls] = []
                objects_by_class[cls].append(obj)

        # validate collections of objects of each Model type
        model_errors = []
        for cls, cls_objects in objects_by_class.items():
            error = cls.validate_unique(cls_objects)
            if error:
                model_errors.append(error)

        # return errors
        if object_errors or model_errors:
            return InvalidObjectSet(object_errors, model_errors)

        return None


def excel_col_name(col):
    """ Convert column number to an Excel-style string.

    From http://stackoverflow.com/a/19169180/509882

    Args:
        col (:obj:`int`): column number (positive integer)

    Returns:
        :obj:`str`: alphabetic column name

    Raises:
        :obj:`ValueError`: if `col` is not positive
    """
    LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    if not isinstance(col, int) or col < 1:
        raise ValueError(
            "excel_col_name: col ({}) must be a positive integer".format(col))

    result = []
    while col:
        col, rem = divmod(col - 1, 26)
        result[:0] = LETTERS[rem]
    return ''.join(result)


class ObjTablesWarning(UserWarning):
    """ :obj:`obj_tables` warning """
    pass


class SchemaWarning(ObjTablesWarning):
    """ Schema warning """
    pass

from .utils import get_related_models
