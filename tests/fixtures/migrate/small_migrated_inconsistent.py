from obj_tables import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TableFormat)

import obj_tables


class Test(obj_tables.Model):
    """ Test

    Related attributes:
        property (:obj:`Property`): property
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id',)


class Property(obj_tables.Model):
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'value')
