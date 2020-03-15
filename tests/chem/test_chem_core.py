""" Test chemistry attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_tables import core
from wc_utils.util import chem
import bcforms
import bpforms
import obj_tables.chem
import openbabel
import unittest


class EmpiricalFormulaAttributeTestCase(unittest.TestCase):

    def test(self):
        attr = obj_tables.chem.EmpiricalFormulaAttribute()
        primary_attr = obj_tables.chem.EmpiricalFormulaAttribute(primary=True, unique=True)
        self.assertEqual(attr.default, None)

        attr = obj_tables.chem.EmpiricalFormulaAttribute(default='C1H1O2')
        self.assertEqual(attr.default, chem.EmpiricalFormula('C1H1O2'))

        attr = obj_tables.chem.EmpiricalFormulaAttribute(default=chem.EmpiricalFormula('C1H1O2'))
        self.assertEqual(attr.default, chem.EmpiricalFormula('C1H1O2'))

        class Node(core.Model):
            value = obj_tables.chem.EmpiricalFormulaAttribute()

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

        attr2 = obj_tables.chem.EmpiricalFormulaAttribute(primary=True)
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


class ChemicalStructureTestCase(unittest.TestCase):
    def test__init__None(self):
        s = obj_tables.chem.ChemicalStructure()
        self.assertEqual(s._value, None)
        self.assertEqual(s._serialized_format, None)
        self.assertEqual(s._serialized_value, None)
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_format, None)
        self.assertEqual(s.serialized_value, None)

    def test__init__str(self):
        serialized_value = 'O'
        s = obj_tables.chem.ChemicalStructure('{}:{}'.format('smiles', serialized_value))
        conv = openbabel.OBConversion()
        conv.SetOutFormat('smiles')
        conv.SetOptions('c', conv.OUTOPTIONS)
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.serialized_value, serialized_value)

    def test__init__openbabel(self):
        mol = openbabel.OBMol()

        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.serialized_value, None)

        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.serialized_value, None)

        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.inchi)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.inchi)
        self.assertEqual(s.serialized_value, None)

        with self.assertRaisesRegex(ValueError, 'must be consistent with `value'):
            obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.bpforms)

    def test__init__bpforms(self):
        mol = bpforms.DnaForm()

        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bpforms)
        self.assertEqual(s.serialized_value, None)

        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.bpforms)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bpforms)
        self.assertEqual(s.serialized_value, None)

        mol2 = bpforms.BpForm()
        with self.assertRaisesRegex(ValueError, 'BpForms must use one of the defined alphabets'):
            obj_tables.chem.ChemicalStructure(mol2)

        with self.assertRaisesRegex(ValueError, 'must be consistent with `value`'):
            obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.bcforms)

    def test__init__bcforms(self):
        mol = bcforms.BcForm()

        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bcforms)
        self.assertEqual(s.serialized_value, None)

        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.bcforms)
        self.assertEqual(s.value, mol)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bcforms)
        self.assertEqual(s.serialized_value, None)

        with self.assertRaisesRegex(ValueError, 'must be consistent with `value`'):
            obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.bpforms)

    def test__init__unsupported_type(self):
        with self.assertRaisesRegex(ValueError, 'Unable to set `value`'):
            obj_tables.chem.ChemicalStructure(1)

    def test__init__inconsistent_format(self):
        with self.assertRaisesRegex(ValueError, 'must be consistent with `value`'):
            obj_tables.chem.ChemicalStructure(None, obj_tables.chem.ChemicalStructureFormat.inchi)

    def test_set_value(self):
        s = obj_tables.chem.ChemicalStructure()
        s.value = openbabel.OBMol()
        s.value = bpforms.DnaForm()
        s.value = openbabel.OBMol()
        s.value = bcforms.BcForm()

    def test_to_dict_None(self):
        s = obj_tables.chem.ChemicalStructure()
        self.assertEqual(s.to_dict(), {
            'format': None,
            'value': None,
        })

    def test_to_dict_openbabel(self):
        mol = openbabel.OBMol()
        conv = openbabel.OBConversion()
        conv.SetInFormat('smi')
        conv.ReadString(mol, 'O')

        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.to_dict(), {
            'format': 'smiles',
            'value': 'O',
        })

        s.serialized_format = obj_tables.chem.ChemicalStructureFormat.inchi
        self.assertEqual(s.to_dict(), {
            'format': 'inchi',
            'value': 'InChI=1S/H2O/h1H2',
        })

        s._serialized_value = 'XXX'
        self.assertEqual(s.to_dict(), {
            'format': 'inchi',
            'value': 'XXX',
        })

    def test_to_dict_bpforms(self):
        seq = 'ACGT'
        mol = bpforms.DnaForm().from_str(seq)

        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.to_dict(), {
            'format': 'bpforms/dna',
            'value': seq,
        })
        self.assertEqual(s.to_dict(), {
            'format': 'bpforms/dna',
            'value': seq,
        })

    def test_to_dict_bcforms(self):
        serialized_value = '2 * a + 3 * b'
        mol = bcforms.BcForm().from_str(serialized_value)

        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.to_dict(), {
            'format': 'bcforms',
            'value': serialized_value,
        })

    def test_serialize_openbabel(self):
        serialized_value = 'InChI=1S/H2O/h1H2'
        mol = openbabel.OBMol()
        conv = openbabel.OBConversion()
        conv.SetInFormat('inchi')
        conv.ReadString(mol, serialized_value)
        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.inchi)
        self.assertEqual(s.serialize(), '{}: {}'.format('inchi', serialized_value))

    def test_serialize_bpforms(self):
        seq = 'ACGU'
        mol = bpforms.RnaForm().from_str(seq)
        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.serialize(), '{}/{}: {}'.format('bpforms', 'rna', seq))

    def test_serialize_bcforms(self):
        serialized_value = '2 * a + 3 * b'
        mol = bcforms.BcForm().from_str(serialized_value)
        s = obj_tables.chem.ChemicalStructure(mol)
        self.assertEqual(s.serialize(), '{}: {}'.format('bcforms', serialized_value))

    def test_from_dict_none(self):
        s = obj_tables.chem.ChemicalStructure()

        s.from_dict({})
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_value, None)
        self.assertEqual(s.serialized_format, None)

        s.from_dict({'format': None})
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_value, None)
        self.assertEqual(s.serialized_format, None)

        s.from_dict({'value': None})
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_value, None)
        self.assertEqual(s.serialized_format, None)

        s.from_dict({'format': None, 'value': None})
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_value, None)
        self.assertEqual(s.serialized_format, None)

        s.from_dict({'format': None, 'value': ''})
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_value, None)
        self.assertEqual(s.serialized_format, None)

        with self.assertRaisesRegex(ValueError, 'key must be defined'):
            s.from_dict({'value': 'O'})

    def test_from_dict_openbabel(self):
        serialized_value = 'O'
        s = obj_tables.chem.ChemicalStructure()
        s.from_dict({'format': 'smiles', 'value': serialized_value})
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        conv = openbabel.OBConversion()
        conv.SetOutFormat('smiles')
        conv.SetOptions('c', conv.OUTOPTIONS)
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)

        serialized_value = 'InChI=1S/H2O/h1H2'
        s = obj_tables.chem.ChemicalStructure()
        s.from_dict({'format': 'inchi', 'value': serialized_value})
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.inchi)
        conv = openbabel.OBConversion()
        conv.SetOutFormat('inchi')
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)

    def test_from_dict_bpforms(self):
        serialized_value = 'ACDE'
        s = obj_tables.chem.ChemicalStructure()
        s.from_dict({'format': 'bpforms/protein', 'value': serialized_value})
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bpforms)
        self.assertEqual(s.value.alphabet, bpforms.protein_alphabet)
        self.assertEqual(str(s.value), serialized_value)

    def test_from_dict_bcforms(self):
        serialized_value = '2 * a'
        s = obj_tables.chem.ChemicalStructure()
        s.from_dict({'format': 'bcforms', 'value': serialized_value})
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bcforms)
        self.assertEqual(str(s.value), serialized_value)

    def test_deserialize_none(self):
        s = obj_tables.chem.ChemicalStructure()

        s.deserialize(None)
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_format, None)
        self.assertEqual(s.serialized_value, None)

        s.deserialize('')
        self.assertEqual(s.value, None)
        self.assertEqual(s.serialized_format, None)
        self.assertEqual(s.serialized_value, None)

    def test_deserialize_openbabel(self):
        serialized_value = 'O'
        s = obj_tables.chem.ChemicalStructure()
        s.deserialize('{}: {}'.format('smiles', serialized_value))
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        conv = openbabel.OBConversion()
        conv.SetOutFormat('smiles')
        conv.SetOptions('c', conv.OUTOPTIONS)
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)

        serialized_value = 'InChI=1S/H2O/h1H2'
        s = obj_tables.chem.ChemicalStructure()
        s.deserialize('{}: {}'.format('inchi', serialized_value))
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.inchi)
        conv = openbabel.OBConversion()
        conv.SetOutFormat('inchi')
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)

    def test_deserialize_bpforms(self):
        serialized_value = 'ACDE'
        s = obj_tables.chem.ChemicalStructure()
        s.deserialize('{}/{}: {}'.format('bpforms', 'protein', serialized_value))
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bpforms)
        self.assertEqual(s.value.alphabet, bpforms.protein_alphabet)
        self.assertEqual(str(s.value), serialized_value)

    def test_deserialize_bcforms(self):
        serialized_value = '2 * a'
        s = obj_tables.chem.ChemicalStructure()
        s.deserialize('{}: {}'.format('bcforms', serialized_value))
        self.assertEqual(s.serialized_value, serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.bcforms)
        self.assertEqual(str(s.value), serialized_value)


class ChemicalStructureAttributeTestCase(unittest.TestCase):
    def test__init__(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()
        primary_attr = obj_tables.chem.ChemicalStructureAttribute(primary=True, unique=True)

    def test_deserialize(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()

        serialized_value = 'O'
        return_value = attr.deserialize('{}: {}'.format('smiles', serialized_value))
        self.assertEqual(return_value[0].serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(return_value[0].serialized_value, serialized_value)
        conv = openbabel.OBConversion()
        conv.SetOutFormat('smiles')
        conv.SetOptions('c', conv.OUTOPTIONS)
        self.assertEqual(conv.WriteString(return_value[0].value, True), serialized_value)
        self.assertEqual(return_value[1], None)

        self.assertEqual(attr.deserialize('O')[0], None)
        self.assertNotEqual(attr.deserialize('O')[1], None)

        self.assertEqual(attr.deserialize(''), (None, None))

        self.assertEqual(attr.deserialize(None), (None, None))

        self.assertEqual(attr.deserialize(1)[0], None)
        self.assertNotEqual(attr.deserialize(1)[1], None)

    def test_serialize(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()

        serialized_value = 'O'
        mol = openbabel.OBMol()
        conv = openbabel.OBConversion()
        conv.SetInFormat('smiles')
        conv.ReadString(mol, serialized_value)
        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(attr.serialize(s), '{}: {}'.format('smiles', serialized_value))
        self.assertEqual(attr.serialize('',), '')
        self.assertEqual(attr.serialize(None), '')

    def test_validate(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()
        primary_attr = obj_tables.chem.ChemicalStructureAttribute(primary=True, unique=True)

        mol = bpforms.DnaForm().from_str('AC')
        s = obj_tables.chem.ChemicalStructure(mol)

        self.assertEqual(attr.validate(None, s), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertNotEqual(attr.validate(None, 1), None)

        self.assertNotEqual(primary_attr.validate(None, None), None)

    def test_validate_unique(self):
        attr = obj_tables.chem.ChemicalStructureAttribute(primary=True, unique=True)

        mol1 = bpforms.DnaForm().from_str('AC')
        mol2 = bpforms.DnaForm().from_str('GT')
        mol3 = bpforms.DnaForm().from_str('AC')
        s1 = obj_tables.chem.ChemicalStructure(mol1)
        s2 = obj_tables.chem.ChemicalStructure(mol2)
        s3 = obj_tables.chem.ChemicalStructure(mol3)
        self.assertEqual(attr.validate_unique(None, [s1, s2]), None)
        self.assertNotEqual(attr.validate_unique(None, [s1, s3]), None)

    def test_to_builtin(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()

        serialized_value = 'O'
        mol = openbabel.OBMol()
        conv = openbabel.OBConversion()
        conv.SetInFormat('smiles')
        conv.ReadString(mol, serialized_value)
        s = obj_tables.chem.ChemicalStructure(mol, obj_tables.chem.ChemicalStructureFormat.smiles)

        self.assertEqual(attr.to_builtin(s), {
            'format': 'smiles',
            'value': serialized_value,
        })
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)

    def test_from_builtin(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()

        serialized_value = 'O'
        s = attr.from_builtin({'format': 'smiles', 'value': serialized_value})
        conv = openbabel.OBConversion()
        conv.SetOutFormat('smiles')
        conv.SetOptions('c', conv.OUTOPTIONS)
        self.assertEqual(conv.WriteString(s.value, True), serialized_value)
        self.assertEqual(s.serialized_format, obj_tables.chem.ChemicalStructureFormat.smiles)
        self.assertEqual(s.serialized_value, serialized_value)

        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)

    def test_get_excel_validation(self):
        attr = obj_tables.chem.ChemicalStructureAttribute()
        attr.get_excel_validation()

        attr = obj_tables.chem.ChemicalStructureAttribute(primary=True, unique=True)
        attr.get_excel_validation()
