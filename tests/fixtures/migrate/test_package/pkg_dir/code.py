import obj_model
from obj_model import SlugAttribute
import module_not_in_test_package

class Foo(obj_model.Model):
    id = SlugAttribute()

    class Meta(obj_model.Model.Meta):
        attribute_order = ('id',)