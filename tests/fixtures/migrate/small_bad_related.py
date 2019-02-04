from obj_model import (Model, BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation)


class Reference(Model):
    """ Reference

    Related attributes:
        tests (:obj:`list` of `Test`): tests
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(Model.Meta):
        attribute_order = ('id', 'value')


class Test(Model):
    """ Test

    Related attributes:
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    name = StringAttribute(default='my name')
    references = ManyToManyAttribute(Reference, related_name='tests')

    class Meta(Model.Meta):
        attribute_order = ('id', 'name', 'references')
        tabular_orientation = TabularOrientation.column


class Reference(Model):
    """ Another definition of Reference, which causes a _check_related_attributes error

    Related attributes:
        subtests (:obj:`list` of `Subtest`): subtests
    """
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(Model.Meta):
        attribute_order = ('id', 'value')


class Subtest(Model):
    """ Subtest
    """
    id = SlugAttribute()
    test = ManyToOneAttribute(Test, related_name='subtests')
    references = ManyToManyAttribute(Reference, related_name='subtests')

    class Meta(Model.Meta):
        attribute_order = ('id', 'test', 'references')
