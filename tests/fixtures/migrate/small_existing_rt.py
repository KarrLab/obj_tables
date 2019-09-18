import re

from obj_tables import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation)

import obj_tables


class Test(obj_tables.Model):
    """ Test

    Related attributes:
        property (:obj:`Property`): property
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    name = StringAttribute(default='test')
    version = RegexAttribute(min_length=1, pattern=r'^[0-9]+\.[0-9+]\.[0-9]+', flags=re.I)
    revision = StringAttribute(default='0.0')
    existing_attr = StringAttribute(default='existing_attr_val')

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'name', 'version', 'revision', 'existing_attr')
        table_format = TabularOrientation.column


class Property(obj_tables.Model):
    id = SlugAttribute()
    test = OneToOneAttribute(Test, related_name='property')
    value = PositiveIntegerAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'test', 'value')
        table_format = TabularOrientation.column


class Subtest(obj_tables.Model):
    id = SlugAttribute()
    test = ManyToOneAttribute(Test, related_name='subtests')
    references = ManyToManyAttribute('Reference', related_name='subtests')

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'test', 'references')


class Reference(obj_tables.Model):
    """ Reference

    Related attributes:
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'value')
