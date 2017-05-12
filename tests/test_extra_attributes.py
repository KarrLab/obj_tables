""" Test extra attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_model import core
from obj_model import extra_attributes
import Bio.Alphabet
import Bio.Seq
import json
import sympy
import unittest


class TestExtraAttribute(unittest.TestCase):

    def test_BioSeqAttribute(self):
        class Node(core.Model):
            value = extra_attributes.BioSeqAttribute()

        attr = Node.Meta.attributes['value']

        # clean
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = None
        alphabet.size = None
        self.assertEqual(attr.clean(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": "", "size": ""}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = 'ACGT'
        alphabet.size = 1
        self.assertEqual(attr.clean(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": "ACGT", "size": 1}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = ['AC', 'GT']
        alphabet.size = 2
        self.assertEqual(attr.clean(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": ["AC", "GT"], "size": 2}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = None
        alphabet.size = 1
        self.assertEqual(attr.clean(
            '{"seq": "ATCG", "alphabet": {"type": "ProteinAlphabet", "letters": "", "size": 1}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = 'ARG'
        alphabet.size = 1
        self.assertEqual(attr.clean(
            '{"seq": "ATCG", "alphabet": {"type": "ProteinAlphabet", "letters": "ARG", "size": 1}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        # serialize
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(json.loads(attr.serialize(Bio.Seq.Seq(''))), {
                         "seq": "", "alphabet": {"type": "Alphabet", "letters": None, "size": None}})
        self.assertEqual(json.loads(attr.serialize(Bio.Seq.Seq('ACGT'))), {
                         "seq": "ACGT", "alphabet": {"type": "Alphabet", "letters": None, "size": None}})

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = 'ACGT'
        alphabet.size = 1
        self.assertEqual(json.loads(attr.serialize(Bio.Seq.Seq('ACGT', alphabet))), {
                         "seq": "ACGT", "alphabet": {"type": "Alphabet", "letters": "ACGT", "size": 1}})

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = ['AC', 'GT']
        alphabet.size = 2
        self.assertEqual(json.loads(attr.serialize(Bio.Seq.Seq('ACGT', alphabet))), {
                         "seq": "ACGT", "alphabet": {"type": "Alphabet", "letters": ["AC", "GT"], "size": 2}})

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = ['AC', 'GT']
        alphabet.size = 2
        self.assertEqual(json.loads(attr.serialize(Bio.Seq.Seq('ACGT', alphabet))), {
                         "seq": "ACGT", "alphabet": {"type": "ProteinAlphabet", "letters": ["AC", "GT"], "size": 2}})

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, None), None)
        self.assertNotEqual(attr.validate(node, ''), None)
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('')), None)

        attr.min_length = 2
        attr.max_length = 4
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('A')), None)
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('ACG')), None)
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ACGTA')), None)

        # validate_unique
        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('CC')]
        self.assertEqual(attr.validate_unique(nodes, values), None)

        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('AA')]
        self.assertNotEqual(attr.validate_unique(nodes, values), None)

    def test_BioDnaRnaProteinSeqAttribute(self):
        class Node(core.Model):
            value = extra_attributes.BioProteinSeqAttribute()

        attr = Node.Meta.attributes['value']

        # clean
        self.assertEqual(attr.clean(''), (None, None))
        self.assertEqual(attr.clean(None), (None, None))
        self.assertEqual(attr.clean('ARG'), (Bio.Seq.Seq('ARG', Bio.Alphabet.ProteinAlphabet()), None))

        # serialize
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(Bio.Seq.Seq('', Bio.Alphabet.ProteinAlphabet())), '')
        self.assertEqual(attr.serialize(Bio.Seq.Seq('ARG', Bio.Alphabet.ProteinAlphabet())), 'ARG')

        # validate
        node = Node()
        self.assertEqual(attr.validate(node, None), None)
        self.assertNotEqual(attr.validate(node, ''), None)
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ARG')), None)
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('ARG', Bio.Alphabet.ProteinAlphabet())), None)

        attr.min_length = 2
        attr.max_length = 4
        alphabet = Bio.Alphabet.ProteinAlphabet()
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('A', alphabet)), None)
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('ACG', alphabet)), None)
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ACGTA', alphabet)), None)

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = 'ARG'
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ACG', alphabet)), None)

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.size = 2
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ACG', alphabet)), None)

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
