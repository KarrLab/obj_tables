""" Test chemistry attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_model import core
from wc_utils.util import chem
import obj_model.chem
import unittest


class ChemAttributeTestCase(unittest.TestCase):

    def test_empirical_formula_attribute(self):
        attr = obj_model.chem.EmpiricalFormulaAttribute()
        primary_attr = obj_model.chem.EmpiricalFormulaAttribute(primary=True, unique=True)
        self.assertEqual(attr.default, None)

        attr = obj_model.chem.EmpiricalFormulaAttribute(default='C1H1O2')
        self.assertEqual(attr.default, chem.EmpiricalFormula('C1H1O2'))

        attr = obj_model.chem.EmpiricalFormulaAttribute(default=chem.EmpiricalFormula('C1H1O2'))
        self.assertEqual(attr.default, chem.EmpiricalFormula('C1H1O2'))

        class Node(core.Model):
            value = obj_model.chem.EmpiricalFormulaAttribute()

        attr = Node.Meta.attributes['value']

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize('X'), (chem.EmpiricalFormula('X'), None))
        self.assertEqual(attr.deserialize('x')[0], None)
        self.assertNotEqual(attr.deserialize('x')[1], None)

        # serialize
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(chem.EmpiricalFormula('C1HO2')), 'CHO2')

        # deserialize + serialize
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize(None)[0]), '')
        self.assertEqual(attr.serialize(attr.deserialize('CHO2')[0]), 'CHO2')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, None), None)
        self.assertEqual(attr.validate(node, chem.EmpiricalFormula('C1HO2')), None)
        self.assertNotEqual(attr.validate(node, ''), None)
        self.assertNotEqual(attr.validate(node, 'x'), None)
        self.assertNotEqual(attr.validate(node, 1), None)

        attr2 = obj_model.chem.EmpiricalFormulaAttribute(primary=True)
        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, chem.EmpiricalFormula('C')), None)
        self.assertNotEqual(attr2.validate(None, None), None)
        self.assertEqual(attr2.validate(None, chem.EmpiricalFormula('C')), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [chem.EmpiricalFormula('CHO2'), chem.EmpiricalFormula('C2HO2')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [chem.EmpiricalFormula('CHO2'), chem.EmpiricalFormula('C1HO2')]), None)

        # to/from JSON
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)
        self.assertEqual(attr.to_builtin(chem.EmpiricalFormula('CHO2')), {'C': 1, 'H': 1, 'O': 2})
        self.assertEqual(attr.to_builtin(chem.EmpiricalFormula('C1HO2')), {'C': 1, 'H': 1, 'O': 2})
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)
        self.assertEqual(attr.from_builtin('CHO2'), chem.EmpiricalFormula('CHO2'))
        self.assertEqual(attr.from_builtin('C1HO2'), chem.EmpiricalFormula('CHO2'))
        self.assertEqual(attr.from_builtin({'C': 1, 'H': 1, 'O': 2}), chem.EmpiricalFormula('CHO2'))
        self.assertEqual(attr.from_builtin({'C': 1, 'H': 1, 'O': 2}), chem.EmpiricalFormula('C1HO2'))

        # get_excel_validation
        attr.get_excel_validation()
        primary_attr.get_excel_validation()

    def test_structure_attribute(self):
        attr = obj_model.chem.ChemicalStructureAttribute()
        primary_attr = obj_model.chem.ChemicalStructureAttribute(primary=True, unique=True)

        smiles = '[OH2]'
        self.assertEqual(attr.deserialize(smiles), (smiles, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertNotEqual(attr.deserialize(1)[1], None)

        # serialize
        self.assertEqual(attr.serialize(smiles), smiles)
        self.assertEqual(attr.serialize('',), '')
        self.assertEqual(attr.serialize(None), '')

        # validate
        self.assertEqual(attr.validate(None, smiles), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertNotEqual(attr.validate(None, 1), None)

        self.assertNotEqual(primary_attr.validate(None, None), None)
        self.assertNotEqual(primary_attr.validate(None, ''), None)

        # validate_unique
        self.assertEqual(primary_attr.validate_unique(None, ['a', 'b']), None)
        self.assertNotEqual(primary_attr.validate_unique(None, ['b', 'b']), None)

        # to_builtin
        self.assertEqual(attr.to_builtin(smiles), smiles)
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)

        # from_builtin
        self.assertEqual(attr.from_builtin(smiles), smiles)
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)

        # get_excel_validation
        attr.get_excel_validation()
        primary_attr.get_excel_validation()
