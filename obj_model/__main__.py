""" Command line programs for migrating data files whose data models are defined using obj_model

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2019-05-13
:Copyright: 2019, Karr Lab
:License: MIT
"""

from cement import Controller, App, ex
import os
import sys

import obj_model
from obj_model import migrate


# todo: import schema controllers into the controllers for schema repos
# todo: import data controllers into the controllers for data repos
class BaseController(Controller):
    """ Base controller for command line application """

    class Meta:
        label = 'base'
        description = "Command line utilities for migrating data files whose data models are defined using obj_model"
        arguments = [
            (['-v', '--version'],
            dict(action='version', version=obj_model.__version__)),
        ]

    @ex(hide=True)
    def _default(self):
        self._parser.print_help()


class SchemaChangesTemplateController(Controller):
    """ Create a schema changes file template """

    class Meta:
        label = 'make_changes_template'
        stacked_on = 'base'
        stacked_type = 'embedded'

    @ex(
        help='Create a schema changes file template',
        arguments = [
            (['schema_url'], {'type': str, 'help': 'URL of the schema repo'}),
            (['--commit'], {'type': str, 'help': 'hash of the last commit containing the changes; default is most recent commit'})
        ]
    )
    def make_changes_template(self):
        args = self.app.pargs
        '''
        clone the URL
        error if the schema changes file template doesn't exists or the commit doesn't exist
        create schema changes file template
        commit & push the change
        output the URL for the template, and pointer to instructions to complete it
        '''
        print('args.schema_url', args.schema_url)
        print('args.commit', args.commit)


class AutomatedMigrationConfigController(Controller):
    """ Create a migration config file """

    class Meta:
        label = 'make_migration_config_file'
        stacked_on = 'base'
        stacked_type = 'embedded'

    @ex(
        help='Create a migration config file',
        arguments = [
            (['schema_url'], {'type': str, 'help': 'URL of the schema in its git repository'}),
            (['file_to_migrate'],
                dict(action='store', type=str, nargs='+',
                help='a file to migrate')),
        ]
    )
    def make_migration_config_file(self):
        args = self.app.pargs
        '''
        clone the schema URL
        error if the schema URL cannot be cloned or imported
        error if any of the files_to_migrate cannot be found
        error if the migration config file exists
        create the migration config file, with the schema in the name
        output the path to the config file, and give instructions to commit it
        '''
        # todo: figure out how to specify the migrator
        print('args.schema_url', args.schema_url)
        print('files to migrate:')
        for f in args.file_to_migrate:
            print('\t', f)


class App(App):
    """ Command line application """
    class Meta:
        label = 'obj-model'
        base_controller = 'base'
        handlers = [
            BaseController,
            SchemaChangesTemplateController,
            AutomatedMigrationConfigController
        ]


def main():
    with App() as app:
        app.run()

if __name__ == '__main__':
    main()
