from obj_model import Model, SlugAttribute, StringAttribute, IntegerAttribute, PositiveIntegerAttribute

class Test(Model):
    id = SlugAttribute()
    name = StringAttribute(default='test')
    existing_attr = StringAttribute()
    size = IntegerAttribute()

class Property(Model):
    id = SlugAttribute()
    value = PositiveIntegerAttribute()
