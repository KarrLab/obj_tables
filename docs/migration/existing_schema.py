from obj_model import (Model, SlugAttribute, StringAttribute,
    FloatAttribute, PositiveIntegerAttribute)

class Test(Model):
    id = SlugAttribute()
    name = StringAttribute(default='test')
    existing_attr = StringAttribute()
    size = FloatAttribute()
    color = StringAttribute()

class Property(Model):
    id = SlugAttribute()
    value = PositiveIntegerAttribute()
