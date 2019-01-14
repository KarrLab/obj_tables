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
        cls.Ontology = pronto.Ontology('tests/fixtures/SBO.obo')
        cls.term = cls.Ontology['SBO:0000000']

    def test_init(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        with self.assertRaisesRegex(ValueError, 'be an instance of `pronto.Ontology`'):
            attr = obj_model.ontology.OntologyAttribute('NOT_AN_ONTOLOGY')

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=[self.Ontology['SBO:0000001']])
        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=self.Ontology['SBO:0000001'].rchildren())
        attr = obj_model.ontology.OntologyAttribute(
            self.Ontology, terms=[self.Ontology['SBO:0000001']] + self.Ontology['SBO:0000001'].rchildren())
        with self.assertRaisesRegex(ValueError, 'must be in `ontology`'):
            attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=['SBO:0000001'])

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, default=self.term)
        attr = obj_model.ontology.OntologyAttribute(self.Ontology, default=self.term, terms=[self.Ontology['SBO:0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.Ontology, default='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.Ontology, default=self.term, terms=[self.Ontology['SBO:0000001']])

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, default_cleaned_value=self.term)
        attr = obj_model.ontology.OntologyAttribute(self.Ontology, default_cleaned_value=self.term, terms=[self.Ontology['SBO:0000000']])
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(self.Ontology, default_cleaned_value='NOT_A_TERM')
        with self.assertRaisesRegex(ValueError, 'must be `None` or in `terms`'):
            attr = obj_model.ontology.OntologyAttribute(
                self.Ontology, default_cleaned_value=self.term, terms=[self.Ontology['SBO:0000001']])

    def test_clean(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.clean('SBO:0000000'), (self.term, None))

        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.clean(None), (None, None))

        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.clean(''), (None, None))

        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=[self.term])
        self.assertEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=[])
        self.assertNotEqual(attr.clean(self.term)[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, default_cleaned_value=self.term)
        self.assertEqual(attr.clean(None)[0].id, self.term.id)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertNotEqual(attr.clean('NOT_A_TERM')[1], None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertNotEqual(attr.clean(pronto.term.Term('NOT_A_TERM'))[1], None)

    def test_validate(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.validate(None, self.term), None)
        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, 'SBO:0000000'), None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, none=False)
        self.assertNotEqual(attr.validate(None, None), None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=[self.term])
        self.assertEqual(attr.validate(None, self.term), None)

        attr = obj_model.ontology.OntologyAttribute(self.Ontology, terms=[])
        self.assertNotEqual(attr.validate(None, self.term), None)

    def test_serialize(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.serialize(self.term), 'SBO:0000000')
        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(''), '')

    def test_deserialize(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.deserialize('SBO:0000000')[0].id, 'SBO:0000000')
        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertEqual(attr.deserialize(''), (None, None))

    def test_to_builtin(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.to_builtin(self.term), 'SBO:0000000')
        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(''), None)

    def test_from_builtin(self):
        attr = obj_model.ontology.OntologyAttribute(self.Ontology)
        self.assertEqual(attr.from_builtin('SBO:0000000').id, 'SBO:0000000')
        self.assertEqual(attr.from_builtin(None), None)
        self.assertEqual(attr.from_builtin(''), None)
