""" Test abstract model functionality

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-23
:Copyright: 2017, Karr Lab
:License: MIT
"""

import obj_tables.abstract
import obj_tables.core
import unittest


class Child(obj_tables.core.Model):
    name = obj_tables.core.SlugAttribute()


class A_Abc(obj_tables.abstract.AbstractModel):
    name = obj_tables.core.SlugAttribute()
    children = obj_tables.core.OneToManyAttribute(Child, related_name='parent')

    @obj_tables.abstract.abstractmethod
    def abstract_method(self, x, y=None):
        pass


class A_Still_Abc(A_Abc):
    long_name = obj_tables.core.LongStringAttribute()
    pass


class A_Concrete_1(A_Still_Abc):

    def abstract_method(self, x, y=None):
        return x


class A_Concrete_2(A_Abc):

    def abstract_method(self, x, y=None):
        return 2 * x


class TestModelAbc(unittest.TestCase):

    def test_cannot_construct_A_Abc(self):
        self.assertRaises(TypeError, A_Abc)

    def test_cannot_construct_A_Still_Abc(self):
        self.assertRaises(TypeError, A_Still_Abc)

    def test_can_construct_A_Concrete_1(self):
        children = [
            Child(name='child_1'),
            Child(name='child_2')
        ]
        parent = A_Concrete_1(
            name='parent_1',
            long_name='parent 1',
            children=children)

        self.assertEqual(parent.name, 'parent_1')
        self.assertEqual(parent.long_name, 'parent 1')
        self.assertEqual(parent.children[0].name, 'child_1')
        self.assertEqual(parent.children[1].name, 'child_2')
        self.assertEqual(parent.children[0].parent, parent)
        self.assertEqual(parent.children[1].parent, parent)
        self.assertEqual(parent.abstract_method(1), 1)

    def test_can_construct_A_Concrete_2(self):
        obj = A_Concrete_2()
        self.assertEqual(obj.abstract_method(1), 2)
