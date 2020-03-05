""" Test math attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_tables import core
import mock
import obj_tables.math.symbolic
import sympy
import unittest


class MathAttributeTestCase(unittest.TestCase):
    def test_SymbolicBasicAttribute(self):
        class Node(core.Model):
            value = obj_tables.math.symbolic.SymbolicBasicAttribute()

        attr = Node.Meta.attributes['value']

        # constructor
        attr2 = obj_tables.math.symbolic.SymbolicBasicAttribute(default=None)
        self.assertEqual(attr2.get_default(), None)

        attr2 = obj_tables.math.symbolic.SymbolicBasicAttribute(default=sympy.Basic('x'))
        self.assertEqual(attr2.get_default(), sympy.Basic('x'))

        with self.assertRaisesRegex(ValueError, 'Default must be a '):
            obj_tables.math.symbolic.SymbolicBasicAttribute(default='x')

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize('x'), (sympy.Basic('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Basic('x')), 'x')

        # deserialize + serialize
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize(None)[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize('x')[0]), 'x')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, ''), None)
        self.assertEqual(attr.validate(node, None), None)
        self.assertEqual(attr.validate(node, sympy.Basic('x')), None)
        self.assertNotEqual(attr.validate(node, 'x'), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr2 = obj_tables.math.symbolic.SymbolicBasicAttribute()
            self.assertEqual(attr2.validate(obj, None), None)

        attr2 = obj_tables.math.symbolic.SymbolicBasicAttribute(primary=True)
        self.assertNotEqual(attr2.validate(node, ''), None)
        self.assertNotEqual(attr2.validate(node, None), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('y')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('x')]), None)

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(sympy.Basic('x')), 'x')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin('x'), sympy.Basic('x'))
        self.assertEqual(attr.from_builtin(attr.to_builtin(sympy.Basic('x'))), sympy.Basic('x'))

    def test_SymbolicExprAttribute(self):
        class Node(core.Model):
            value = obj_tables.math.symbolic.SymbolicExprAttribute()

        attr = Node.Meta.attributes['value']

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize('x'), (sympy.Expr('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Expr('x')), 'x')

        # deserialize + serialize
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize(None)[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize('x')[0]), 'x')

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

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(sympy.Expr('x')), 'x')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin('x'), sympy.Expr('x'))
        self.assertEqual(attr.from_builtin(attr.to_builtin(sympy.Expr('x'))), sympy.Expr('x'))

    def test_SymbolicSymbolAttribute(self):
        class Node(core.Model):
            value = obj_tables.math.symbolic.SymbolicSymbolAttribute()

        attr = Node.Meta.attributes['value']

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize('x'), (sympy.Symbol('x'), None))

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(sympy.Symbol('x')), 'x')

        # deserialize + serialize
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize(None)[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize('x')[0]), 'x')

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

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(sympy.Symbol('x')), 'x')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin('x'), sympy.Symbol('x'))
        self.assertEqual(attr.from_builtin(attr.to_builtin(sympy.Symbol('x'))), sympy.Symbol('x'))
