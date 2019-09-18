""" Test examples

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-18
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_model import io
from obj_model import utils
import obj_model
import unittest


class ExamplesTestCase(unittest.TestCase):
    def test_web_app_example(self):
        filename = 'obj_model/web_app/examples/parents_children.xlsx'
        sbtab = True

        schema = utils.init_schema(filename, sbtab=sbtab)
        models = list(utils.get_models(schema).values())

        io.Reader().run(filename,
                        models=models,
                        group_objects_by_model=False,
                        sbtab=sbtab,
                        **io.SBTAB_DEFAULT_READER_OPTS)
