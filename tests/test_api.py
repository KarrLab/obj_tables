"""
:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2018-03-12
:Copyright: 2018, Karr Lab
:License: MIT
"""

import obj_tables
import types
import unittest


class ApiTestCase(unittest.TestCase):
    def test(self):
        self.assertIsInstance(obj_tables.Model, type)
