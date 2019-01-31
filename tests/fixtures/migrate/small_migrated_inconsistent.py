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

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id',)


class Property(obj_model.Model):
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'value')
