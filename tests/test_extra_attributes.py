""" Test extra attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

import sympy
from obj_model import core
from obj_model import extra_attributes
import unittest


class TestExtraAttribute(unittest.TestCase):

    def test_SympyBasicAttribute(self):
        class Node(core.Model):
            value = extra_attributes.SympyBasicAttribute()

        attr = Node.Meta.attributes['value']

        # clean
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean('x'), (sympy.Basic('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Basic('x')), 'x')

        # clean + serialize
        self.assertEqual(attr.serialize(attr.clean('')[0]), '')
        self.assertEqual(attr.serialize(attr.clean(None)[0]), '')
        self.assertEqual(attr.serialize(attr.clean('x')[0]), 'x')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, ''), None)
        self.assertEqual(attr.validate(node, None), None)
        self.assertEqual(attr.validate(node, sympy.Basic('x')), None)
        self.assertNotEqual(attr.validate(node, 'x'), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('y')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('x')]), None)

    def test_SympyExprAttribute(self):
        class Node(core.Model):
            value = extra_attributes.SympyExprAttribute()

        attr = Node.Meta.attributes['value']

        # clean
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean('x'), (sympy.Expr('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Expr('x')), 'x')

        # clean + serialize
        self.assertEqual(attr.serialize(attr.clean('')[0]), '')
        self.assertEqual(attr.serialize(attr.clean(None)[0]), '')
        self.assertEqual(attr.serialize(attr.clean('x')[0]), 'x')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, ''), None)
        self.assertEqual(attr.validate(node, None), None)
        self.assertEqual(attr.validate(node, sympy.Expr('x')), None)
        self.assertNotEqual(attr.validate(node, 'x'), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [sympy.Expr('x'), sympy.Expr('y')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [sympy.Expr('x'), sympy.Expr('x')]), None)

    def test_SympySymbolAttribute(self):
        class Node(core.Model):
            value = extra_attributes.SympySymbolAttribute()

        attr = Node.Meta.attributes['value']

        # clean
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean('x'), (sympy.Symbol('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Symbol('x')), 'x')

        # clean + serialize
        self.assertEqual(attr.serialize(attr.clean('')[0]), '')
        self.assertEqual(attr.serialize(attr.clean(None)[0]), '')
        self.assertEqual(attr.serialize(attr.clean('x')[0]), 'x')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, ''), None)
        self.assertEqual(attr.validate(node, None), None)
        self.assertEqual(attr.validate(node, sympy.Symbol('x')), None)
        self.assertNotEqual(attr.validate(node, 'x'), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [sympy.Symbol('x'), sympy.Symbol('y')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [sympy.Symbol('x'), sympy.Symbol('x')]), None)
