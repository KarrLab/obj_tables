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
import pandas
import unittest


class ArrayAttributeTestCase(unittest.TestCase):
    def test(self):
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


class TableAttributeTestCase(unittest.TestCase):
    def test__init__(self):
        attr = obj_tables.math.numeric.TableAttribute()
        self.assertEqual(attr.get_default(), None)

        default_values = {'a': [1, 2]}
        default = pandas.DataFrame(default_values)
        attr = obj_tables.math.numeric.TableAttribute(default=default)
        self.assertTrue(attr.get_default().equals(default))

        with self.assertRaisesRegex(ValueError, '`default` must be a `pandas.DataFrame` or `None`'):
            obj_tables.math.numeric.TableAttribute(default=default_values)

    def test_validate(self):
        attr = obj_tables.math.numeric.TableAttribute()
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, []), None)

        attr = obj_tables.math.numeric.TableAttribute(default=pandas.DataFrame({'a': [1, 2]}))
        self.assertEqual(attr.validate(None, pandas.DataFrame({'a': [1, 2]}).astype(numpy.int64)), None)
        self.assertNotEqual(attr.validate(None, pandas.DataFrame({'a': [1., 2.]})), None)

        attr = obj_tables.math.numeric.TableAttribute(primary=True)
        self.assertNotEqual(attr.validate(None, None), None)

    def test_validate_unique(self):
        attr = obj_tables.math.numeric.TableAttribute()

        self.assertEqual(attr.validate_unique([], [
            pandas.DataFrame({'a': [1, 2]}),
            pandas.DataFrame({'a': [3, 4]}),
        ]), None)

        self.assertEqual(attr.validate_unique([], [
            pandas.DataFrame({'a': [1, 2]}),
            None,
        ]), None)

        self.assertNotEqual(attr.validate_unique([], [
            pandas.DataFrame({'a': [1, 2]}),
            pandas.DataFrame({'a': [1, 2]}),
        ]), None)

        self.assertNotEqual(attr.validate_unique([], [None, None]), None)

    def test_serialize_deserialize(self):
        attr = obj_tables.math.numeric.TableAttribute()

        value = pandas.DataFrame({'a': [1, 2], 'b': [3, 4]})
        deserialized_value, error = attr.deserialize(attr.serialize(value))
        self.assertEqual(error, None)
        self.assertTrue(deserialized_value.equals(value))
        self.assertEqual(deserialized_value.values.dtype.type, numpy.int64)

        value = pandas.DataFrame({'a': [1., 2.], 'b': [3., 4.]})
        deserialized_value, error = attr.deserialize(attr.serialize(value))
        self.assertEqual(error, None)
        self.assertTrue(deserialized_value.equals(value))
        self.assertEqual(deserialized_value.values.dtype.type, numpy.float64)

    def test_deserialize(self):
        attr = obj_tables.math.numeric.TableAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))

        value, error = attr.deserialize('{"a": {"0": 1, "1": 2}, "_index": [0, 1]}')
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1, 2]})))
        self.assertEqual(error, None)

        value, error = attr.deserialize('{"a": {"0": 1.0, "1": 2.0}, "_index": [0, 1]}')
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(error, None)

        value, error = attr.deserialize({'a': [1., 2.], '_index': [0, 1]})
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(error, None)

        value, error = attr.deserialize(pandas.DataFrame({'a': [1., 2.]}))
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(error, None)

        attr = obj_tables.math.numeric.TableAttribute(default=pandas.DataFrame({'a': [1., 2.]}))

        value, error = attr.deserialize('{"a": {"0": 1, "1": 2}, "_index": [0, 1]}')
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(value.values.dtype.type, numpy.float64)
        self.assertEqual(error, None)

        value, error = attr.deserialize({'a': [1, 2], '_index': [0, 1]})
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(value.values.dtype.type, numpy.float64)
        self.assertEqual(error, None)

        value, error = attr.deserialize(pandas.DataFrame({'a': [1., 2.]}))
        self.assertTrue(value.equals(pandas.DataFrame({'a': [1., 2.]})))
        self.assertEqual(value.values.dtype.type, numpy.float64)
        self.assertEqual(error, None)

        self.assertNotEqual(attr.deserialize('x')[1], None)
        self.assertNotEqual(attr.deserialize(1.)[1], None)

        _, error = attr.deserialize({'a': [1., 2.], 'b': [3.], '_index': [0, 1]})
        self.assertNotEqual(error, None)

    def test_to_from_builtin(self):
        attr = obj_tables.math.numeric.TableAttribute()
        self.assertEqual(attr.to_builtin(None), None)

        raw_value = {'a': [1, 2], 'b': [3, 4]}
        value = pandas.DataFrame(raw_value)

        dict_value = {'a': {0: 1, 1: 2}, 'b': {0: 3, 1: 4}, '_index': [0, 1]}
        self.assertEqual(attr.to_builtin(value), dict_value)

        self.assertEqual(attr.from_builtin(None), None)
        self.assertTrue(attr.from_builtin(dict_value).equals(value))
        self.assertTrue(attr.from_builtin(attr.to_builtin(value)).equals(value))

        raw_value = {'a': [1., 2.], 'b': [3., 4.]}
        value = pandas.DataFrame(raw_value)
        attr = obj_tables.math.numeric.TableAttribute(default=value)
        self.assertTrue(attr.from_builtin(attr.to_builtin(value)).equals(value))
