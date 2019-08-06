# an example transformations program
from obj_model.migrate import MigrationWrapper

class TransformationExample(MigrationWrapper):

    def prepare_existing_models(self, migrator, existing_models):
        """ Prepare existing models before migration

        Convert `Test.size` values to integers before they are migrated
        
        Args:
            migrator (:obj:`Migrator`:) the `Migrator` calling this method
            existing_models (:obj:`list` of `obj_model.Model`:) the models
                that will be migrated
        """
        for existing_model in existing_models:
            if isinstance(existing_model, migrator.existing_defs['Test']):
                existing_model.size = int(existing_model.size)

    def modify_migrated_models(self, migrator, migrated_models):
        """ Modify migrated models after migration

        Args:
            migrator (:obj:`Migrator`:) the `Migrator` calling this method
            migrated_models (:obj:`list` of `obj_model.Model`:) all models
                that have been migrated
        """
        pass

# a MigrationWrapper subclass instance must be assigned to `transformations`
transformations = TransformationExample()
