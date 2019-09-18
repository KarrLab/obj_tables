# import packages that should be loaded as obj_tables requires them
import networkx
import numpy


from obj_tables import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
                       PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute,
                       LongStringAttribute, UrlAttribute, OneToOneAttribute, ManyToOneAttribute,
                       ManyToManyAttribute, OneToManyAttribute, TabularOrientation)
import obj_tables
from test_package.pkg_dir.code import Foo


class Test(obj_tables.Model):
    id = SlugAttribute()
    name = StringAttribute(default='test')
    revision = StringAttribute(default='0.0')
    existing_attr = StringAttribute(default='existing_attr_val')
    references = ManyToManyAttribute('Reference', related_name='tests')

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'name', 'revision', 'existing_attr')
        table_format = TabularOrientation.column


class Reference(obj_tables.Model):
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id', 'value')
