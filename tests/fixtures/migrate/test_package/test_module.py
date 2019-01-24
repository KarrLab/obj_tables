# import packages that should be loaded as obj_model requires them
import networkx
import numpy


from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation)

import obj_model

from test_package.pkg_dir.code import Foo
'''
from .pkg_dir import code
from ..test_package.pkg_dir import code
'''


class Test(obj_model.Model):
    id = SlugAttribute()
    name = StringAttribute(default='test')
    revision = StringAttribute(default='0.0')
    existing_attr = StringAttribute(default='existing_attr_val')

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'name', 'revision', 'existing_attr')
        tabular_orientation = TabularOrientation.column


class Reference(obj_model.Model):
    id = SlugAttribute()
    value = StringAttribute()
    
    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'value')
