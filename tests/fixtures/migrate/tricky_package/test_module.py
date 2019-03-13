# import packages that should be loaded as obj_model requires them
import networkx
import numpy


from obj_model import SlugAttribute, StringAttribute, ManyToManyAttribute, TabularOrientation
import obj_model


class Test(obj_model.Model):
    id = SlugAttribute()
    name = StringAttribute(default='test')
    revision = StringAttribute(default='0.0')
    existing_attr = StringAttribute(default='existing_attr_val')
    references = ManyToManyAttribute('Reference', related_name='tests')

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'name', 'revision', 'existing_attr')
        tabular_orientation = TabularOrientation.column


class Reference(obj_model.Model):
    id = SlugAttribute()
    value = StringAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id', 'value')
