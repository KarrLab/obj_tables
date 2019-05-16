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
