import re

from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation)

import obj_model


class Test(obj_model.Model):
    """ Test

    Related attributes:
        property (:obj:`Property`): property
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    name = StringAttribute(default='test')
    version = RegexAttribute(min_length=1, pattern=r'^[0-9]+\.[0-9+]\.[0-9]+', flags=re.I)
    revision = StringAttribute(default='0.0')
    migrated_attr = obj_model.core.StringAttribute(default='foo')

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'name', 'version', 'revision', 'migrated_attr')
        tabular_orientation = TabularOrientation.column


class NewModel(obj_model.Model):
    id = SlugAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id',)


class Property(obj_model.Model):
    id = SlugAttribute()
    test = OneToOneAttribute(Test, related_name='property')
    value = PositiveIntegerAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'test', 'value')
        tabular_orientation = TabularOrientation.column


class Subtest(obj_model.Model):
    id = SlugAttribute()
    test = ManyToOneAttribute(Test, related_name='subtests')
    references = ManyToManyAttribute('Reference', related_name='subtests')

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'test', 'references')


class Reference(obj_model.Model):
    """ Reference

    Related attributes:
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'value')
