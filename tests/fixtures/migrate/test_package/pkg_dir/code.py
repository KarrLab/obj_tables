import obj_tables
from obj_tables import SlugAttribute

class Foo(obj_tables.Model):
    id = SlugAttribute()

    class Meta(obj_tables.Model.Meta):
        attribute_order = ('id',)