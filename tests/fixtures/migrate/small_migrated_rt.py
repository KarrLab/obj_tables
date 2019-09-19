import re

from obj_tables import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TableFormat)

import obj_tables


class MigratedTest(obj_tables.Model):
    """ Test

    Related attributes:
        property (:obj:`Property`): property
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    name = StringAttribute(default='test')
    version = RegexAttribute(min_length=1, pattern=r'^[0-9]+\.[0-9+]\.[0-9]+', flags=re.I)
    revision = StringAttribute(default='0.0')
    migrated_attr = obj_tables.core.StringAttribute(default='foo')

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'name', 'version', 'revision', 'migrated_attr')
        table_format = TableFormat.column


class Property(obj_tables.Model):
    id = SlugAttribute()
    test = OneToOneAttribute(MigratedTest, related_name='property')
    migrated_value = PositiveIntegerAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'test', 'migrated_value')
        table_format = TableFormat.column


class Subtest(obj_tables.Model):
    id = SlugAttribute()
    test = ManyToOneAttribute(MigratedTest, related_name='subtests')
    migrated_references = ManyToManyAttribute('Reference', related_name='subtests')

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'test', 'migrated_references')


class Reference(obj_tables.Model):
    """ Reference

    Related attributes:
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'value')
