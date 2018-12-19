""" Test math attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_model import core
import mock
import numpy
import obj_model.math
import sympy
import unittest


class MathAttributeTestCase(unittest.TestCase):
    def test_SympyBasicAttribute(self):
        class Node(core.Model):
            value = obj_model.math.SympyBasicAttribute()

        attr = Node.Meta.attributes['value']

        # constructor
        attr2 = obj_model.math.SympyBasicAttribute(default=None)
        self.assertEqual(attr2.get_default(), None)

        attr2 = obj_model.math.SympyBasicAttribute(default=sympy.Basic('x'))
        self.assertEqual(attr2.get_default(), sympy.Basic('x'))

        with self.assertRaisesRegex(ValueError, 'Default must be a '):
            obj_model.math.SympyBasicAttribute(default='x')

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
            attr2 = obj_model.math.SympyBasicAttribute()
            self.assertEqual(attr2.validate(obj, None), None)

        attr2 = obj_model.math.SympyBasicAttribute(primary=True)
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

    def test_NumpyArrayAttribute(self):
        # constructor
        attr = obj_model.math.NumpyArrayAttribute()
        self.assertEqual(attr.get_default(), None)

        attr = obj_model.math.NumpyArrayAttribute(default=numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.get_default(), numpy.array([1, 2]))

        with self.assertRaisesRegex(ValueError, '`default` must be a `numpy.array` or `None`'):
            obj_model.math.NumpyArrayAttribute(default=[1, 2])

        with self.assertRaisesRegex(ValueError, '`min_length` must be a non-negative integer'):
            obj_model.math.NumpyArrayAttribute(min_length=-1)

        with self.assertRaisesRegex(ValueError, '`max_length` must be an integer greater than or equal to `min_length`'):
            obj_model.math.NumpyArrayAttribute(min_length=10, max_length=5)

        # deserialize
        attr = obj_model.math.NumpyArrayAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize([1., 2., 3.]), (numpy.array([1., 2., 3.]), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1., 2., 3.])), (numpy.array([1., 2., 3.]), None))

        attr = obj_model.math.NumpyArrayAttribute(default=numpy.ones((1, 1)))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize([1, 2, 3]), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1, 2, 3])), (numpy.array([1., 2., 3.], numpy.float64), None))

        self.assertNotEqual(attr.deserialize('x')[1], None)
        self.assertNotEqual(attr.deserialize(1.)[1], None)

        # validate
        attr = obj_model.math.NumpyArrayAttribute()
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, []), None)

        attr = obj_model.math.NumpyArrayAttribute(default=numpy.array([1., 2.], numpy.float64))
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2], numpy.int64)), None)

        attr = obj_model.math.NumpyArrayAttribute(min_length=2, max_length=5)
        self.assertEqual(attr.validate(None, numpy.array([1, 2])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2, 3, 4, 5, 6])), None)

        attr = obj_model.math.NumpyArrayAttribute(primary=True)
        self.assertNotEqual(attr.validate(None, None), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr = obj_model.math.NumpyArrayAttribute()
            self.assertEqual(attr.validate(obj, None), None)

        # validate unique
        attr = obj_model.math.NumpyArrayAttribute()
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([2, 3])]), None)
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), None]), None)
        self.assertNotEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([1, 2])]), None)
        self.assertNotEqual(attr.validate_unique([], [None, None]), None)

        # serialize
        attr = obj_model.math.NumpyArrayAttribute()
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1, 2])))[0], numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1., 2.])))[0], numpy.array([1., 2.]))

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(numpy.array([1, 2])), [1, 2])
        self.assertEqual(attr.from_builtin(None), None)
        numpy.testing.assert_equal(attr.from_builtin([1, 2]), numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.from_builtin(attr.to_builtin(numpy.array([1, 2]))), numpy.array([1, 2]))

        attr = obj_model.math.NumpyArrayAttribute(primary=True, default=numpy.array([1.1, 2.2]))
        numpy.testing.assert_equal(attr.from_builtin([1, 2]), numpy.array([1, 2]))

    def test_SympyExprAttribute(self):
        class Node(core.Model):
            value = obj_model.math.SympyExprAttribute()

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

    def test_SympySymbolAttribute(self):
        class Node(core.Model):
            value = obj_model.math.SympySymbolAttribute()

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
