""" Test biological attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-10
:Copyright: 2017, Karr Lab
:License: MIT
"""

from obj_tables import core
import Bio.Alphabet
import Bio.motifs.matrix
import Bio.Seq
import Bio.SeqFeature
import json
import mock
import obj_tables.bio
import unittest


class BioAttributeTestCase(unittest.TestCase):

    def test_FeatureLocationAttribute(self):
        # construction
        attr = obj_tables.bio.FeatureLocationAttribute()
        self.assertEqual(attr.get_default(), None)

        attr = obj_tables.bio.FeatureLocationAttribute(default=Bio.SeqFeature.FeatureLocation(10, 10, 1))
        self.assertEqual(attr.get_default(), Bio.SeqFeature.FeatureLocation(10, 10, 1))

        with self.assertRaisesRegex(ValueError, '`default` must be a `Bio.SeqFeature.FeatureLocation`'):
            obj_tables.bio.FeatureLocationAttribute(default='')

        # deserialize
        attr = obj_tables.bio.FeatureLocationAttribute()
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize('10,10,1'), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize((10, 10, 1)), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize([10, 10, 1]), (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize(Bio.SeqFeature.FeatureLocation(10, 10, 1)),
                         (Bio.SeqFeature.FeatureLocation(10, 10, 1), None))
        self.assertEqual(attr.deserialize(1)[0], None)
        self.assertNotEqual(attr.deserialize(1)[1], None)

        # validate
        obj = None
        attr = obj_tables.bio.FeatureLocationAttribute()
        self.assertEqual(attr.validate(obj, None), None)
        self.assertEqual(attr.validate(obj, Bio.SeqFeature.FeatureLocation(10, 10, 1)), None)
        self.assertNotEqual(attr.validate(obj, 1), None)

        attr = obj_tables.bio.FeatureLocationAttribute(primary=True)
        self.assertNotEqual(attr.validate(obj, None), None)

        with mock.patch.object(core.Attribute, 'validate', return_value=core.InvalidAttribute(None, [])):
            obj = None
            attr = obj_tables.bio.FeatureLocationAttribute()
            self.assertEqual(attr.validate(obj, None), None)

        # validate unique
        attr = obj_tables.bio.FeatureLocationAttribute()
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
        attr = obj_tables.bio.FeatureLocationAttribute()
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(Bio.SeqFeature.FeatureLocation(10, 10, 1)), '10,10,1')

        self.assertEqual(attr.serialize(attr.deserialize('10,10,1')[0]), '10,10,1')
        self.assertEqual(attr.serialize(attr.deserialize('')[0]), '')

        # to/from JSON
        ft = Bio.SeqFeature.FeatureLocation(100, 200, 1)
        ft2 = {
            'start': 100,
            'end': 200,
            'strand': 1,
        }
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(ft), ft2)
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(ft2), ft)
        self.assertEqual(attr.from_builtin(attr.to_builtin(ft)), ft)

    def test_BioSeqAttribute(self):
        class Node(core.Model):
            value = obj_tables.bio.BioSeqAttribute()

        attr = Node.Meta.attributes['value']

        # constructor
        attr2 = obj_tables.bio.BioSeqAttribute(default=None)
        self.assertEqual(attr2.get_default(), None)

        attr2 = obj_tables.bio.BioSeqAttribute(default=Bio.Seq.Seq('acgt'))
        self.assertEqual(attr2.get_default(), Bio.Seq.Seq('acgt'))

        with self.assertRaisesRegex(ValueError, '`default` must be a `Bio.Seq.Seq` or `None`'):
            obj_tables.bio.BioSeqAttribute(default='acgt')

        with self.assertRaisesRegex(ValueError, '`min_length` must be a non-negative integer'):
            obj_tables.bio.BioSeqAttribute(min_length=-1)

        with self.assertRaisesRegex(ValueError, '`max_length` must be an integer greater than or equal to `min_length`'):
            obj_tables.bio.BioSeqAttribute(min_length=10, max_length=5)

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

        attr2 = obj_tables.bio.BioSeqAttribute(primary=True)
        self.assertNotEqual(attr2.validate(None, None), None)

        # validate_unique
        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('CC')]
        self.assertEqual(attr.validate_unique(nodes, values), None)

        nodes = [Node(), Node()]
        values = [Bio.Seq.Seq('AA'), Bio.Seq.Seq('AA')]
        self.assertNotEqual(attr.validate_unique(nodes, values), None)

        # to/from JSON
        seq = Bio.Seq.Seq('AA')
        seq2 = {
            'seq': 'AA',
            'alphabet': {
                'type': 'Alphabet',
                'letters': None,
                'size': None,
            }
        }
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(seq), seq2)
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(seq2), seq)
        self.assertEqual(attr.from_builtin(attr.to_builtin(seq)), seq)

    def test_BioDnaSeqAttribute(self):
        attr = obj_tables.bio.BioDnaSeqAttribute()
        self.assertEqual(attr.alphabet.letters, Bio.Alphabet.DNAAlphabet().letters)

        # to/from JSON
        alphabet = Bio.Alphabet.DNAAlphabet()
        seq = Bio.Seq.Seq('AA', alphabet=alphabet)
        seq2 = {
            'seq': 'AA',
            'alphabet': {
                'type': 'DNAAlphabet',
                'letters': alphabet.letters,
                'size': alphabet.size,
            }
        }
        self.assertEqual(attr.to_builtin(seq), seq2)
        self.assertEqual(attr.from_builtin(seq2), seq)
        self.assertEqual(attr.from_builtin(attr.to_builtin(seq)), seq)

    def test_BioRnaSeqAttribute(self):
        attr = obj_tables.bio.BioRnaSeqAttribute()
        self.assertEqual(attr.alphabet.letters, Bio.Alphabet.RNAAlphabet().letters)

        # to/from JSON
        alphabet = Bio.Alphabet.RNAAlphabet()
        seq = Bio.Seq.Seq('AA', alphabet=alphabet)
        seq2 = {
            'seq': 'AA',
            'alphabet': {
                'type': 'RNAAlphabet',
                'letters': alphabet.letters,
                'size': alphabet.size,
            }
        }
        self.assertEqual(attr.to_builtin(seq), seq2)
        self.assertEqual(attr.from_builtin(seq2), seq)
        self.assertEqual(attr.from_builtin(attr.to_builtin(seq)), seq)

    def test_BioProteinSeqAttribute(self):
        class Node(core.Model):
            value = obj_tables.bio.BioProteinSeqAttribute()

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

        # to/from JSON
        alphabet = Bio.Alphabet.ProteinAlphabet()
        seq = Bio.Seq.Seq('AA', alphabet=alphabet)
        seq2 = {
            'seq': 'AA',
            'alphabet': {
                'type': 'ProteinAlphabet',
                'letters': alphabet.letters,
                'size': alphabet.size,
            }
        }
        self.assertEqual(attr.to_builtin(seq), seq2)
        self.assertEqual(attr.from_builtin(seq2), seq)
        self.assertEqual(attr.from_builtin(attr.to_builtin(seq)), seq)

    def test_FrequencyPositionMatrixAttribute(self):
        attr = obj_tables.bio.FrequencyPositionMatrixAttribute()

        alphabet = Bio.Alphabet.DNAAlphabet()
        alphabet.letters = 'ACGT'
        alphabet.size = 4
        letter_counts = {
            'A': [1, 2, 3],
            'C': [4, 5, 6],
            'G': [7, 8, 9],
            'T': [10, 11, 12],
        }
        mat = Bio.motifs.matrix.FrequencyPositionMatrix(alphabet, letter_counts)

        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, mat), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertNotEqual(attr.validate(None, 1), None)
        self.assertNotEqual(attr.validate(None, []), None)

        self.assertEqual(attr.deserialize(attr.serialize(None)), (None, None))

        self.assertEqual(attr.deserialize(attr.serialize(mat)), (mat, None))
        self.assertEqual(attr.deserialize(attr.serialize(mat))[0].alphabet.letters, 'ACGT')
        self.assertEqual(sorted(attr.deserialize(attr.serialize(mat))[0].keys()), ['A', 'C', 'G', 'T'])
        self.assertEqual(attr.deserialize(attr.serialize(mat))[0]['A'], letter_counts['A'])
        self.assertEqual(attr.deserialize(attr.serialize(mat))[0]['C'], letter_counts['C'])
        self.assertEqual(attr.deserialize(attr.serialize(mat))[0]['G'], letter_counts['G'])
        self.assertEqual(attr.deserialize(attr.serialize(mat))[0]['T'], letter_counts['T'])

        self.assertEqual(attr.deserialize('x')[0], None)
        self.assertNotEqual(attr.deserialize('x')[1], None)

        # to/from JSON
        mat2 = {
            'A': letter_counts['A'],
            'C': letter_counts['C'],
            'G': letter_counts['G'],
            'T': letter_counts['T'],
            '_alphabet': {
                'type': 'DNAAlphabet',
                'letters': 'ACGT',
                'size': 4,
            },
        }
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(mat), mat2)
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(mat2), mat)
        self.assertEqual(attr.from_builtin(attr.to_builtin(mat)), mat)
