""" Test unit attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-20
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables import units
from wc_utils.util.units import unit_registry
import pint
import unittest


class UnitAttributeTestCase(unittest.TestCase):
    def test_init(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry,
                                   choices=[registry.parse_units('s'), registry.parse_units('g')],
                                   default=registry.parse_units('s'),
                                   default_cleaned_value=registry.parse_units('g'))
        self.assertEqual(len(attr.choices), 2)

        attr = units.UnitAttribute(registry)
        self.assertEqual(attr.choices, None)

        with self.assertRaisesRegex(ValueError, '`registry` must be an instance of'):
            units.UnitAttribute('registry')
        with self.assertRaisesRegex(ValueError, '`default` must be an instance of'):
            units.UnitAttribute(registry, default='s')
        with self.assertRaisesRegex(ValueError, '`default_cleaned_value` must be an instance of'):
            units.UnitAttribute(registry, default_cleaned_value='g')
        with self.assertRaisesRegex(ValueError, 'choices must be instances of'):
            units.UnitAttribute(registry, choices=['g'])

    def test_get_default(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry, default=registry.parse_units('s'))
        self.assertEqual(attr.get_default(), registry.parse_units('s'))

    def test_get_default_cleaned_value(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry, default_cleaned_value=registry.parse_units('g'))
        self.assertEqual(attr.get_default_cleaned_value(), registry.parse_units('g'))

    def test_value_equal(self):
        registry1 = unit_registry
        registry2 = pint.UnitRegistry()
        registry3 = pint.UnitRegistry()
        attr = units.UnitAttribute(unit_registry)

        self.assertTrue(attr.value_equal(registry1.parse_units('g'), registry1.parse_units('g')))
        self.assertFalse(attr.value_equal(registry1.parse_units('g'), registry2.parse_units('g')))
        self.assertTrue(attr.value_equal(registry1.parse_units('g'), registry1.parse_units('g / l * l')))
        self.assertFalse(attr.value_equal(registry1.parse_units('g'), registry2.parse_units('g / l * l')))
        self.assertTrue(attr.value_equal(registry1.parse_units('M'), registry1.parse_units('mol / l')))
        self.assertTrue(attr.value_equal(None, None))
        self.assertFalse(attr.value_equal(None, registry1.parse_units('mol / l')))
        self.assertFalse(attr.value_equal('g', registry1.parse_units('mol / l')))
        self.assertFalse(attr.value_equal(registry1.parse_units('mol / l'), None))
        self.assertFalse(attr.value_equal(registry1.parse_units('g'), registry1.parse_units('l')))
        self.assertFalse(attr.value_equal(registry1.parse_units('ag'), registry1.parse_units('g')))

    def test_clean(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry, default_cleaned_value=registry.parse_units('g'))

        self.assertEqual(attr.clean(''), (registry.parse_units('g'), None))
        self.assertEqual(attr.clean(None), (registry.parse_units('g'), None))
        self.assertEqual(attr.clean('s'), (registry.parse_units('s'), None))
        self.assertEqual(attr.clean('dimensionless'), (registry.parse_units('dimensionless'), None))
        self.assertNotEqual(attr.clean('dimensionless')[0], None)
        self.assertEqual(attr.clean(registry.parse_units('s')), (registry.parse_units('s'), None))
        self.assertNotEqual(attr.clean(1.)[1], None)
        self.assertNotEqual(attr.clean('not_a_unit')[1], None)

        attr = units.UnitAttribute(registry, default_cleaned_value=None)
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean('s'), (registry.parse_units('s'), None))

    def test_validate(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry, choices=[registry.parse_units('s')])

        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, registry.parse_units('s')), None)
        self.assertNotEqual(attr.validate(None, registry.parse_units('g')), None)
        self.assertNotEqual(attr.validate(None, 's'), None)
        self.assertNotEqual(attr.validate(None, 2.), None)

        attr = units.UnitAttribute(registry)
        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, registry.parse_units('s')), None)
        self.assertEqual(attr.validate(None, registry.parse_units('g')), None)

        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry, none=False)
        self.assertNotEqual(attr.validate(None, None), None)

    def test_copy_value(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry)
        unit = registry.parse_units('s')
        self.assertIs(attr.copy_value(unit, {}), unit)

    def test_serialize(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry)

        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(registry.parse_units('s')), 'second')
        self.assertEqual(attr.serialize(registry.parse_units('dimensionless')), 'dimensionless')

    def test_to_builtin(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry)

        self.assertEqual(attr.to_builtin(''), None)
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(registry.parse_units('s')), 'second')

    def test_from_builtin(self):
        registry = pint.UnitRegistry()
        attr = units.UnitAttribute(registry)

        self.assertEqual(attr.from_builtin(''), None)
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin('s'), registry.parse_units('s'))

    def test_get_obj_units(self):
        registry = pint.UnitRegistry()

        class TestModel(core.Model):
            registry = pint.UnitRegistry()
            str_attr = core.StringAttribute()
            unit_attr_1 = units.UnitAttribute(registry)
            unit_attr_2 = units.UnitAttribute(registry)

        units_g = registry.parse_units('g')
        units_l = registry.parse_units('l')
        model = TestModel(str_attr='s',
                          unit_attr_1=units_g,
                          unit_attr_2=units_l)

        self.assertEqual(set(units.get_obj_units(model)), set([units_g, units_l]))
