from obj_model import Model, SlugAttribute, StringAttribute

class MigratedTest(Model):  # Model Test renamed to MigratedTest
    id = SlugAttribute()
    name = StringAttribute(default='test')
    # Attribute Test.existing_attr renamed to MigratedTest.migrated_attr
    migrated_attr = StringAttribute()
    # Attribute MigratedTest.revision added
    revision = StringAttribute(default='0.0')
    # Attribute Test.size removed

# Model Property removed

# Model Reference added
class Reference(Model):
    id = SlugAttribute()
    value = StringAttribute()
