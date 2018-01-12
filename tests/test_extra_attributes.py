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
import Bio.SeqFeature
import json
import mock
import numpy
import sympy
import unittest


class TestExtraAttribute(unittest.TestCase):

    def test_FeatureLocationAttribute(self):
        # construction
        attr = extra_attributes.FeatureLocationAttribute()
        self.assertEqual(attr.get_default(None), None)

        attr = extra_attributes.FeatureLocationAttribute(default=Bio.SeqFeature.FeatureLocation(10, 10, 1))
        self.assertEqual(attr.get_default(None), Bio.SeqFeature.FeatureLocation(10, 10, 1))

        with self.assertRaisesRegexp(ValueError, '`default` must be a `Bio.SeqFeature.FeatureLocation`'):
            extra_attributes.FeatureLocationAttribute(default='')

        # deserialize
        attr = extra_attributes.FeatureLocationAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize('10,10,1'), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize((10,10,1)), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize([10,10,1]), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize(Bio.SeqFeature.FeatureLocation(10, 10, 1)), 
            (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize(1)[0], None)
        self.assertNotEqual(attr.deserialize(1)[1], None)

        # validate
        obj = None
        attr = extra_attributes.FeatureLocationAttribute()
        self.assertEqual(attr.validate(obj, None), None)
        self.assertEqual(attr.validate(obj, Bio.SeqFeature.FeatureLocation(10, 10, 1)), None)
        self.assertNotEqual(attr.validate(obj, 1), None)

        attr = extra_attributes.FeatureLocationAttribute(primary=True)
        self.assertNotEqual(attr.validate(obj, None), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr = extra_attributes.FeatureLocationAttribute()
            self.assertEqual(attr.validate(obj, None), None)

        # validate unique
        attr = extra_attributes.FeatureLocationAttribute()
        self.assertEqual(attr.validate_unique([], [
            Bio.SeqFeature.FeatureLocation(10, 10, 1), 
            None,
            ]), None)
        self.assertEqual(attr.validate_unique([], [
            Bio.SeqFeature.FeatureLocation(10, 10, 1), 
            Bio.SeqFeature.FeatureLocation(1, 10, 1),
            ]), None)
        self.assertNotEqual(attr.validate_unique([], [
            Bio.SeqFeature.FeatureLocation(10, 10, 1),
            Bio.SeqFeature.FeatureLocation(10, 10, 1),
            ]), None)
        self.assertNotEqual(attr.validate_unique([], [
            None, 
            None,
            ]), None)

        # serialize
        attr = extra_attributes.FeatureLocationAttribute()
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(Bio.SeqFeature.FeatureLocation(10, 10, 1)), '10,10,1')

        self.assertEqual(attr.serialize(attr.deserialize('10,10,1')[0]), '10,10,1')
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')


    def test_BioSeqAttribute(self):
        class Node(core.Model):
            value = extra_attributes.BioSeqAttribute()

        attr = Node.Meta.attributes['value']

        # constructor
        attr2 = extra_attributes.BioSeqAttribute(default=None)
        self.assertEqual(attr2.get_default(None), None)

        attr2 = extra_attributes.BioSeqAttribute(default=Bio.Seq.Seq('acgt'))
        self.assertEqual(attr2.get_default(None), Bio.Seq.Seq('acgt'))
        
        with self.assertRaisesRegexp(ValueError, '`default` must be a `Bio.Seq.Seq` or `None`'):
            extra_attributes.BioSeqAttribute(default='acgt')

        with self.assertRaisesRegexp(ValueError, '`min_length` must be a non-negative integer'):
            extra_attributes.BioSeqAttribute(min_length=-1)

        with self.assertRaisesRegexp(ValueError, '`max_length` must be an integer greater than or equal to `min_length`'):
            extra_attributes.BioSeqAttribute(min_length=10, max_length=5)

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = None
        alphabet.size = None
        self.assertEqual(attr.deserialize(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": "", "size": ""}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = 'ACGT'
        alphabet.size = 1
        self.assertEqual(attr.deserialize(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": "ACGT", "size": 1}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.Alphabet()
        alphabet.letters = ['AC', 'GT']
        alphabet.size = 2
        self.assertEqual(attr.deserialize(
            '{"seq": "ATCG", "alphabet": {"type": "Alphabet", "letters": ["AC", "GT"], "size": 2}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = None
        alphabet.size = 1
        self.assertEqual(attr.deserialize(
            '{"seq": "ATCG", "alphabet": {"type": "ProteinAlphabet", "letters": "", "size": 1}}'),
            (Bio.Seq.Seq('ATCG', alphabet), None))

        alphabet = Bio.Alphabet.ProteinAlphabet()
        alphabet.letters = 'ARG'
        alphabet.size = 1
        self.assertEqual(attr.deserialize(
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
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('acgt')), None)

        attr.min_length = 2
        attr.max_length = 4
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('A')), None)
        self.assertEqual(attr.validate(node, Bio.Seq.Seq('ACG')), None)
        self.assertNotEqual(attr.validate(node, Bio.Seq.Seq('ACGTA')), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            self.assertEqual(attr.validate(node, Bio.Seq.Seq('acgt')), None)

        attr2 = extra_attributes.BioSeqAttribute(primary=True)
        self.assertNotEqual(attr2.validate(None, None), None)

        # validate_unique
        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('CC')]
        self.assertEqual(attr.validate_unique(nodes, values), None)

        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('AA')]
        self.assertNotEqual(attr.validate_unique(nodes, values), None)

    def test_BioDnaSeqAttribute(self):
        attr = extra_attributes.BioDnaSeqAttribute()
        self.assertEqual(attr.alphabet.letters, Bio.Alphabet.DNAAlphabet().letters)

    def test_BioRnaSeqAttribute(self):
        attr = extra_attributes.BioRnaSeqAttribute()
        self.assertEqual(attr.alphabet.letters, Bio.Alphabet.RNAAlphabet().letters)

    def test_BioProteinSeqAttribute(self):
        class Node(core.Model):
            value = extra_attributes.BioProteinSeqAttribute()

        attr = Node.Meta.attributes['value']

        # deserialize
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize('ARG'), (Bio.Seq.Seq('ARG', Bio.Alphabet.ProteinAlphabet()), None))

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

        # constructor
        attr2 = extra_attributes.SympyBasicAttribute(default=None)
        self.assertEqual(attr2.get_default(None), None)

        attr2 = extra_attributes.SympyBasicAttribute(default=sympy.Basic('x'))
        self.assertEqual(attr2.get_default(None), sympy.Basic('x'))

        with self.assertRaisesRegexp(ValueError, 'Default must be a '):
            extra_attributes.SympyBasicAttribute(default='x')

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
            attr2 = extra_attributes.SympyBasicAttribute()
            self.assertEqual(attr2.validate(obj, None), None)

        attr2 = extra_attributes.SympyBasicAttribute(primary=True)
        self.assertNotEqual(attr2.validate(node, ''), None)
        self.assertNotEqual(attr2.validate(node, None), None)

        # validate_unique
        nodes = [Node(), Node()]
        self.assertEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('y')]), None)
        self.assertNotEqual(attr.validate_unique(nodes, [sympy.Basic('x'), sympy.Basic('x')]), None)

    def test_NumpyArrayAttribute(self):
        # constructor
        attr = extra_attributes.NumpyArrayAttribute()
        self.assertEqual(attr.get_default(None), None)

        attr = extra_attributes.NumpyArrayAttribute(default=numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.get_default(None), numpy.array([1, 2]))

        with self.assertRaisesRegexp(ValueError, '`default` must be a `numpy.array` or `None`'):
            extra_attributes.NumpyArrayAttribute(default=[1, 2])

        with self.assertRaisesRegexp(ValueError, '`min_length` must be a non-negative integer'):
            extra_attributes.NumpyArrayAttribute(min_length=-1)

        with self.assertRaisesRegexp(ValueError, '`max_length` must be an integer greater than or equal to `min_length`'):
            extra_attributes.NumpyArrayAttribute(min_length=10, max_length=5)

        # deserialize
        attr = extra_attributes.NumpyArrayAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3]), None))
        numpy.testing.assert_equal(attr.deserialize([1., 2., 3.]), (numpy.array([1., 2., 3.]), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1., 2., 3.])), (numpy.array([1., 2., 3.]), None))

        attr = extra_attributes.NumpyArrayAttribute(default=numpy.ones((1, 1)))
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        numpy.testing.assert_equal(attr.deserialize('[1, 2, 3]'), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize((1, 2, 3)), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize([1, 2, 3]), (numpy.array([1, 2, 3], numpy.float64), None))
        numpy.testing.assert_equal(attr.deserialize(numpy.array([1, 2, 3])), (numpy.array([1., 2., 3.], numpy.float64), None))

        self.assertNotEqual(attr.deserialize('x')[1], None)
        self.assertNotEqual(attr.deserialize(1.)[1], None)

        # validate
        attr = extra_attributes.NumpyArrayAttribute()
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, []), None)

        attr = extra_attributes.NumpyArrayAttribute(default=numpy.array([1., 2.], numpy.float64))
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2], numpy.int64)), None)

        attr = extra_attributes.NumpyArrayAttribute(min_length=2, max_length=5)
        self.assertEqual(attr.validate(None, numpy.array([1, 2])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1])), None)
        self.assertNotEqual(attr.validate(None, numpy.array([1, 2, 3, 4, 5, 6])), None)

        attr = extra_attributes.NumpyArrayAttribute(primary=True)
        self.assertNotEqual(attr.validate(None, None), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr = extra_attributes.NumpyArrayAttribute()
            self.assertEqual(attr.validate(obj, None), None)

        # validate unique
        attr = extra_attributes.NumpyArrayAttribute()
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([2, 3])]), None)
        self.assertEqual(attr.validate_unique([], [numpy.array([1, 2]), None]), None)
        self.assertNotEqual(attr.validate_unique([], [numpy.array([1, 2]), numpy.array([1, 2])]), None)
        self.assertNotEqual(attr.validate_unique([], [None, None]), None)

        # serialize
        attr = extra_attributes.NumpyArrayAttribute()
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1, 2])))[0], numpy.array([1, 2]))
        numpy.testing.assert_equal(attr.deserialize(attr.serialize(numpy.array([1., 2.])))[0], numpy.array([1., 2.]))

    def test_SympyExprAttribute(self):
        class Node(core.Model):
            value = extra_attributes.SympyExprAttribute()

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

    def test_SympySymbolAttribute(self):
        class Node(core.Model):
            value = extra_attributes.SympySymbolAttribute()

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
