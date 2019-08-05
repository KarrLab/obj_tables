from obj_model import Model, SlugAttribute, StringAttribute, FloatAttribute

class ChangedTest(Model):  # Model Test renamed to ChangedTest
    id = SlugAttribute()
    name = StringAttribute(default='test')
    # Attribute Test.existing_attr renamed to ChangedTest.migrated_attr
    migrated_attr = StringAttribute()
    # Attribute ChangedTest.revision added
    revision = StringAttribute(default='0.0')
    # Type of attribute Test.size changed to a float
    size = FloatAttribute()
    # Attribute Test.color removed    

# Model Property removed

# Model Reference added
class Reference(Model):
    id = SlugAttribute()
    value = StringAttribute()
