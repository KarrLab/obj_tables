""" Test ontology attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-14
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_model import core
import obj_model.ontology
import pronto
import unittest


class OntologyAttributeTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ontology = pronto.Ontology('tests/fixtures/SBO.obo')
        cls.term = cls.ontology['SBO:0000000']

    def test_init(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        with self.assertRaisesRegex(ValueError, 'be an instance of `pronto.Ontology`'):
            attr = obj_model.ontology.OntologyAttribute('NOT_AN_ONTOLOGY')

        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=[self.ontology['SBO:0000001']])
        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=self.ontology['SBO:0000001'].rchildren())
        attr = obj_model.ontology.OntologyAttribute(
            self.ontology, terms=[self.ontology['SBO:0000001']] + self.ontology['SBO:0000001'].rchildren())
        with self.assertRaisesRegex(ValueError, 'must be in `ontology`'):
            attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=['SBO:0000001'])

        attr = obj_model.ontology.OntologyAttribute(self.ontology, default=self.term)
        attr = obj_model.ontology.OntologyAttribute(self.ontology, default=self.term, terms=[self.ontology['SBO:0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.ontology, default='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.ontology, default=self.term, terms=[self.ontology['SBO:0000001']])

        attr = obj_model.ontology.OntologyAttribute(self.ontology, default_cleaned_value=self.term)
        attr = obj_model.ontology.OntologyAttribute(self.ontology, default_cleaned_value=self.term, terms=[self.ontology['SBO:0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.ontology, default_cleaned_value='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(
                self.ontology, default_cleaned_value=self.term, terms=[self.ontology['SBO:0000001']])

    def test_value_equal(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        
        self.assertTrue(attr.value_equal(self.ontology['SBO:0000000'], self.ontology['SBO:0000000']))        
        self.assertTrue(attr.value_equal(None, None))
        self.assertTrue(attr.value_equal('', ''))

        self.assertFalse(attr.value_equal(self.ontology['SBO:0000000'], None))
        self.assertFalse(attr.value_equal(self.ontology['SBO:0000000'], ''))
        self.assertFalse(attr.value_equal(None, self.ontology['SBO:0000000']))
        self.assertFalse(attr.value_equal('', self.ontology['SBO:0000000']))

    def test_clean(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.clean('SBO:0000000 ! systems biology representation'), (self.term, None))

        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.clean(None), (None, None))

        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.clean(''), (None, None))

        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=[self.term])
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=[])
        self.assertNotEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, default_cleaned_value=self.term)
        self.assertEqual(attr.clean(None)[0].id, self.term.id)

        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertNotEqual(attr.clean('NOT_A_TERM ! NOT_A_TERM')[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertNotEqual(attr.clean(pronto.term.Term('NOT_A_TERM ! NOT_A_TERM'))[1], None)

    def test_validate(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.validate(None, self.term), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, 'SBO:0000000'), None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, none=False)
        self.assertNotEqual(attr.validate(None, None), None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=[self.term])
        self.assertEqual(attr.validate(None, self.term), None)

        attr = obj_model.ontology.OntologyAttribute(self.ontology, terms=[])
        self.assertNotEqual(attr.validate(None, self.term), None)

    def test_copy_value(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.copy_value(self.term, {}), self.term)
        self.assertEqual(attr.copy_value(self.term, {}).id, self.term.id)

    def test_serialize(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.serialize(self.term), 'SBO:0000000 ! systems biology representation')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(''), '')

    def test_deserialize(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.deserialize('SBO:0000000 ! systems biology representation')[0].id, 'SBO:0000000')
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))

    def test_to_builtin(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.to_builtin(self.term), 'SBO:0000000')
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)

    def test_from_builtin(self):
        attr = obj_model.ontology.OntologyAttribute(self.ontology)
        self.assertEqual(attr.from_builtin('SBO:0000000').id, 'SBO:0000000')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)
