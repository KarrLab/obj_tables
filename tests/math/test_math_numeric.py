""" Test math attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_tables import core
import mock
import numpy
import obj_tables.math.numeric
import unittest


class MathAttributeTestCase(unittest.TestCase):
    def test_ArrayAttribute(self):
        # constructor
        attr = obj_tables.math.numeric.ArrayAttribute()
        self.assertEqual(attr.get_default(), None)

        attr = obj_tables.math.numeric.ArrayAttribute(default=numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.get_default(), numpy.array([1, 2]))

        with self.assertRaisesRegex(ValueError, '`default` must be a `numpy.array` or `None`'):
            obj_tables.math.numeric.ArrayAttribute(default=[1, 2])

        with self.assertRaisesRegex(ValueError, '`min_length` must be a non-negative integer'):
            obj_tables.math.numeric.ArrayAttribute(min_length=-1)

        with self.assertRaisesRegex(ValueError, '`max_length` must be an integer greater than or equal to `min_length`'):
            obj_tables.math.numeric.ArrayAttribute(min_length=10, max_length=5)

        # deserialize
        attr = obj_tables.math.numeric.ArrayAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize([1., 2., 3.]), (numpy.array([1., 2., 3.]), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1., 2., 3.])), (numpy.array([1., 2., 3.]), None))

        attr = obj_tables.math.numeric.ArrayAttribute(default=numpy.ones((1, 1)))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize([1, 2, 3]), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1, 2, 3])), (numpy.array([1., 2., 3.], numpy.float64), None))

        self.assertNotEqual(attr.deserialize('x')[1], None)
        self.assertNotEqual(attr.deserialize(1.)[1], None)

        # validate
        attr = obj_tables.math.numeric.ArrayAttribute()
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, []), None)

        attr = obj_tables.math.numeric.ArrayAttribute(default=numpy.array([1., 2.], numpy.float64))
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2], numpy.int64)), None)

        attr = obj_tables.math.numeric.ArrayAttribute(min_length=2, max_length=5)
        self.assertEqual(attr.validate(None, numpy.array([1, 2])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2, 3, 4, 5, 6])), None)

        attr = obj_tables.math.numeric.ArrayAttribute(primary=True)
        self.assertNotEqual(attr.validate(None, None), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr = obj_tables.math.numeric.ArrayAttribute()
            self.assertEqual(attr.validate(obj, None), None)

        # validate unique
        attr = obj_tables.math.numeric.ArrayAttribute()
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([2, 3])]), None)
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), None]), None)
        self.assertNotEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([1, 2])]), None)
        self.assertNotEqual(attr.validate_unique([], [None, None]), None)

        # serialize
        attr = obj_tables.math.numeric.ArrayAttribute()
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1, 2])))[0], numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1., 2.])))[0], numpy.array([1., 2.]))

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(numpy.array([1, 2])), [1, 2])
        self.assertEqual(attr.from_builtin(None), None)
        numpy.testing.assert_equal(attr.from_builtin([1, 2]), numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.from_builtin(attr.to_builtin(numpy.array([1, 2]))), numpy.array([1, 2]))

        attr = obj_tables.math.numeric.ArrayAttribute(primary=True, default=numpy.array([1.1, 2.2]))
        numpy.testing.assert_equal(attr.from_builtin([1, 2]), numpy.array([1, 2]))
