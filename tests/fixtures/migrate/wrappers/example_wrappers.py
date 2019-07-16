from obj_model.migrate import MigrationWrapper

class SimpleWrapper(MigrationWrapper):
    """ Simple, but doesn't follow method signatures of MigrationWrapper """

    def prepare_existing_models(self, a, b):
        return a+b

    def modify_migrated_models(self, a, b):
        return a-b

simple_wrapper = SimpleWrapper()


class InvertingPropertyWrapper(MigrationWrapper):

    # make a transformations with prepare_existing_models & modify_migrated_models that invert each other
    def prepare_existing_models(self, migrator, existing_models):
        # increment the value of Property models
        for existing_model in existing_models:
            if isinstance(existing_model, migrator.existing_defs['Property']):
                existing_model.value += +1

    def modify_migrated_models(self, migrator, migrated_models):
        # decrement the value of Property models
        for migrated_model in migrated_models:
            if isinstance(migrated_model, migrator.existing_defs['Property']):
                migrated_model.value += -1

inverting_property_wrapper = InvertingPropertyWrapper()