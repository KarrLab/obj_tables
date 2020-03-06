""" Test uncertainty attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2020-03-05
:Copyright: 2020, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables.sci import uncertainty
import uncertainties
import unittest


class UncertainFloatAttributeTestCase(unittest.TestCase):
    def test_init(self):
        attr = uncertainty.UncertainFloatAttribute(
            default=uncertainties.ufloat(3, 1),
            default_cleaned_value=uncertainties.ufloat(4, 2))

        with self.assertRaisesRegex(ValueError, '`default` must be an instance of'):
            uncertainty.UncertainFloatAttribute(default='1')
        with self.assertRaisesRegex(ValueError, '`default_cleaned_value` must be an instance of'):
            uncertainty.UncertainFloatAttribute(default_cleaned_value='2')

    def test_get_default(self):
        attr = uncertainty.UncertainFloatAttribute(default=uncertainties.ufloat(3, 2))
        self.assertEqual(attr.get_default().n, 3)
        self.assertEqual(attr.get_default().s, 2)

    def test_get_default_cleaned_value(self):
        attr = uncertainty.UncertainFloatAttribute(default_cleaned_value=uncertainties.ufloat(3, 2))
        self.assertEqual(attr.get_default_cleaned_value().n, 3)
        self.assertEqual(attr.get_default_cleaned_value().s, 2)

    def test_value_equal(self):
        attr = uncertainty.UncertainFloatAttribute()

        self.assertTrue(attr.value_equal(None, None))
        self.assertFalse(attr.value_equal(None, uncertainties.ufloat(3, 2)))
        self.assertFalse(attr.value_equal(uncertainties.ufloat(3, 2), None))
        self.assertTrue(attr.value_equal(uncertainties.ufloat(3, 2), uncertainties.ufloat(3, 2)))
        self.assertFalse(attr.value_equal(uncertainties.ufloat(3, 2), uncertainties.ufloat(3, 1)))
        self.assertTrue(attr.value_equal(
            uncertainties.ufloat(float('nan'), 2),
            uncertainties.ufloat(float('nan'), 2)))
        self.assertTrue(attr.value_equal(
            uncertainties.ufloat(2, float('nan')),
            uncertainties.ufloat(2, float('nan'))))

    def test_clean(self):
        attr = uncertainty.UncertainFloatAttribute(default_cleaned_value=uncertainties.ufloat(3, 2))

        self.assertEqual(attr.clean('')[0].n, 3)
        self.assertEqual(attr.clean('')[0].s, 2)
        self.assertEqual(attr.clean('')[1], None)

        self.assertEqual(attr.clean(None)[0].n, 3)
        self.assertEqual(attr.clean(None)[0].s, 2)
        self.assertEqual(attr.clean(None)[1], None)

        self.assertEqual(attr.clean('4+/-3')[0].n, 4)
        self.assertEqual(attr.clean('4+/- 3')[0].s, 3)
        self.assertEqual(attr.clean('4 +/- 3')[1], None)
        self.assertEqual(attr.clean('4 ± 3')[1], None)

        self.assertNotEqual(attr.clean('4 ±')[1], None)
        self.assertNotEqual(attr.clean(4.)[1], None)

        self.assertEqual(attr.clean(uncertainties.ufloat(4, 3))[0].n, 4)
        self.assertEqual(attr.clean(uncertainties.ufloat(4, 3))[0].s, 3)
        self.assertEqual(attr.clean(uncertainties.ufloat(4, 3))[1], None)

    def test_validate(self):
        attr = uncertainty.UncertainFloatAttribute(none=True)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertEqual(attr.validate(None, uncertainties.ufloat(2, 0.5)), None)
        self.assertNotEqual(attr.validate(None, '2 +/- 5'), None)

        attr = uncertainty.UncertainFloatAttribute(none=False)
        self.assertNotEqual(attr.validate(None, None), None)

    def test_copy_value(self):
        attr = uncertainty.UncertainFloatAttribute()
        orig = uncertainties.ufloat(2, 0.5)
        copy = attr.copy_value(orig, {})
        self.assertIsNot(copy, orig)
        self.assertEqual(copy.n, orig.n)
        self.assertEqual(copy.s, orig.s)

        self.assertEqual(attr.copy_value(None, {}), None)

    def test_serialize(self):
        attr = uncertainty.UncertainFloatAttribute()

        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(uncertainties.ufloat(3., 2.)), '3.0 ± 2.0')

    def test_to_builtin(self):
        attr = uncertainty.UncertainFloatAttribute()

        self.assertEqual(attr.to_builtin(''), None)
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(uncertainties.ufloat(3, 1)), {
            'nominal_value': 3,
            'std_dev': 1,
        })

    def test_from_builtin(self):
        attr = uncertainty.UncertainFloatAttribute()

        self.assertEqual(attr.from_builtin(''), None)
        self.assertEqual(attr.from_builtin(None), None)
        val = attr.from_builtin({'nominal_value': 3, 'std_dev': 1})
        self.assertIsInstance(val, uncertainties.core.Variable)
        self.assertEqual(val.n, 3)
        self.assertEqual(val.s, 1)

    def test_get_excel_validation(self):
        attr = uncertainty.UncertainFloatAttribute(none=True, unique=True)
        attr.get_excel_validation()

        attr = uncertainty.UncertainFloatAttribute(none=False, unique=False,
                                                   default_cleaned_value=uncertainties.ufloat(3, 2))
        attr.get_excel_validation()
