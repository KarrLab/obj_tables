""" Test reference attributes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-20
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables import refs
import json
import unittest


class RefsAttributeTestCase(unittest.TestCase):
    def test_Identifier(self):
        id = refs.Identifier('ns', 'id')
        self.assertEqual(id.namespace, 'ns')
        self.assertEqual(id.id, 'id')

        self.assertEqual(id.to_dict(), {'namespace': 'ns', 'id': 'id'})
        id.from_dict({'namespace': 'ns2', 'id': 'id2'})
        self.assertEqual(id.namespace, 'ns2')
        self.assertEqual(id.id, 'id2')

        self.assertEqual(id.to_str(), "'id2' @ 'ns2'")
        id.from_str("'id3' @ 'ns3'")
        self.assertEqual(id.namespace, 'ns3')
        self.assertEqual(id.id, 'id3')

        with self.assertRaises(ValueError):
            id.from_str("'id3 @ 'ns3'")

    def test_IdentifierAttribute(self):
        attr = refs.IdentifierAttribute()

        id, err = attr.deserialize("'id3' @ 'ns3'")
        self.assertEqual(err, None)
        self.assertEqual(id.namespace, 'ns3')
        self.assertEqual(id.id, 'id3')

        id, err = attr.deserialize("'id3 @ 'ns3'")
        self.assertNotEqual(err, None)
        self.assertEqual(id, None)

        self.assertEqual(attr.deserialize(''), (None, None))
        self.assertEqual(attr.deserialize(None), (None, None))

        id, err = attr.deserialize(1)
        self.assertNotEqual(err, None)
        self.assertEqual(id, None)

        self.assertEqual(attr.validate(None, None), None)
        self.assertEqual(attr.validate(None, refs.Identifier()), None)
        self.assertNotEqual(attr.validate(None, ''), None)

        self.assertEqual(attr.serialize(None), '')
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(refs.Identifier('ns', 'id')), "'id' @ 'ns'")

        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(refs.Identifier('ns', 'id')),
                         {'namespace': 'ns', 'id': 'id'})

        id = attr.from_builtin({'namespace': 'ns', 'id': 'id'})
        self.assertEqual(id.namespace, 'ns')
        self.assertEqual(id.id, 'id')
        self.assertEqual(attr.from_builtin(None), None)

        attr.get_excel_validation()

    def test_IdentifiersAttribute(self):
        attr = refs.IdentifiersAttribute()

        ids, err = attr.deserialize("'id3'@ 'ns3','id4' @'ns4'")
        self.assertEqual(err, None)
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0].namespace, 'ns3')
        self.assertEqual(ids[0].id, 'id3')
        self.assertEqual(ids[1].namespace, 'ns4')
        self.assertEqual(ids[1].id, 'id4')

        id, err = attr.deserialize("'id3 @ 'ns3'")
        self.assertNotEqual(err, None)
        self.assertEqual(id, None)

        self.assertEqual(attr.deserialize(''), ([], None))
        self.assertEqual(attr.deserialize(None), ([], None))

        id, err = attr.deserialize(1)
        self.assertNotEqual(err, None)
        self.assertEqual(id, None)

        self.assertEqual(attr.validate(None, [refs.Identifier()]), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertNotEqual(attr.validate(None, ['']), None)

        self.assertEqual(attr.serialize([]), '')
        self.assertEqual(attr.serialize([refs.Identifier('ns', 'id')]),
                         "'id' @ 'ns'")
        self.assertEqual(attr.serialize([refs.Identifier('ns', 'id'),
                                         refs.Identifier('ns2', 'id2')]),
                         "'id' @ 'ns', 'id2' @ 'ns2'")

        self.assertEqual(attr.to_builtin([]), [])
        self.assertEqual(attr.to_builtin([refs.Identifier('ns', 'id')]),
                         [{'namespace': 'ns', 'id': 'id'}])
        self.assertEqual(attr.to_builtin([refs.Identifier('ns', 'id'),
                                          refs.Identifier('ns2', 'id2')]),
                         [{'namespace': 'ns', 'id': 'id'},
                          {'namespace': 'ns2', 'id': 'id2'}])

        ids = attr.from_builtin([{'namespace': 'ns', 'id': 'id'},
                                 {'namespace': 'ns2', 'id': 'id2'}])
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0].namespace, 'ns')
        self.assertEqual(ids[0].id, 'id')
        self.assertEqual(ids[1].namespace, 'ns2')
        self.assertEqual(ids[1].id, 'id2')

        attr.get_excel_validation()

    def test_DoiAttribute(self):
        doi = "10.1016/j.mib.2015.06.004"
        attr = refs.DoiAttribute()

        doi2, err = attr.deserialize(doi)
        self.assertEqual(err, None)
        self.assertEqual(doi2, doi)

        self.assertEqual(attr.deserialize(''), ('', None))
        self.assertEqual(attr.deserialize(None), ('', None))

        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertEqual(attr.validate(None, doi), None)
        self.assertNotEqual(attr.validate(None, 'doi'), None)
        self.assertNotEqual(attr.validate(None, 1), None)

        self.assertEqual(attr.serialize(None), None)
        self.assertEqual(attr.serialize(''), '')
        self.assertEqual(attr.serialize(doi), doi)

        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(doi), doi)

        self.assertEqual(attr.from_builtin(doi), doi)

        attr.get_excel_validation()

    def test_DoisAttribute(self):
        dois = [
            "10.1016/j.mib.2015.06.004",
            "10.1016/j.mib.2015.06.005",
        ]
        attr = refs.DoisAttribute()

        dois2, err = attr.deserialize(', '.join(dois))
        self.assertEqual(err, None)
        self.assertEqual(dois2, dois)

        self.assertEqual(attr.deserialize(''), ([], None))
        self.assertEqual(attr.deserialize(None), ([], None))
        self.assertNotEqual(attr.deserialize(1)[1], None)

        self.assertEqual(attr.validate(None, dois), None)
        self.assertNotEqual(attr.validate(None, 'doi'), None)
        self.assertNotEqual(attr.validate(None, ['doi']), None)

        self.assertEqual(attr.serialize(dois), ', '.join(dois))
        self.assertEqual(attr.serialize([]), '')

        self.assertEqual(attr.to_builtin(dois), dois)

        self.assertEqual(attr.from_builtin(dois), dois)

        attr.get_excel_validation()

    def test_PubMedIdAttribute(self):
        pmid = 1234
        attr = refs.PubMedIdAttribute()

        pmid2, err = attr.deserialize(pmid)
        self.assertEqual(err, None)
        self.assertEqual(pmid2, pmid)

        self.assertEqual(attr.deserialize(None), (None, None))
        self.assertNotEqual(attr.deserialize(''), ('', None))

        self.assertEqual(attr.validate(None, None), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertEqual(attr.validate(None, pmid), None)
        self.assertNotEqual(attr.validate(None, 'pmid'), None)
        self.assertNotEqual(attr.validate(None, '1'), None)

        self.assertEqual(attr.serialize(None), None)
        self.assertEqual(attr.serialize(pmid), pmid)

        self.assertEqual(attr.to_builtin(None), None)
        self.assertEqual(attr.to_builtin(pmid), pmid)

        self.assertEqual(attr.from_builtin(pmid), pmid)
        self.assertEqual(attr.from_builtin(None), None)

        attr.get_excel_validation()

    def test_PubMedIdsAttribute(self):
        pmids = [1234, 1235]
        attr = refs.PubMedIdsAttribute()

        pmids2, err = attr.deserialize(', '.join(str(pmid) for pmid in pmids))
        self.assertEqual(err, None)
        self.assertEqual(pmids2, pmids)

        self.assertEqual(attr.deserialize(None), ([], None))
        self.assertEqual(attr.deserialize(''), ([], None))
        self.assertNotEqual(attr.deserialize(2)[1], None)
        self.assertNotEqual(attr.deserialize('a')[1], None)
        self.assertNotEqual(attr.deserialize('1.1')[1], None)

        self.assertEqual(attr.validate(None, []), None)
        self.assertNotEqual(attr.validate(None, ''), None)
        self.assertEqual(attr.validate(None, pmids), None)
        self.assertNotEqual(attr.validate(None, ['1']), None)

        self.assertEqual(attr.serialize([]), '')
        self.assertEqual(attr.serialize(pmids), ', '.join(str(pmid) for pmid in pmids))

        self.assertEqual(attr.to_builtin(pmids), pmids)
        self.assertEqual(attr.to_builtin([]), [])

        self.assertEqual(attr.from_builtin(pmids), pmids)
        self.assertEqual(attr.from_builtin([]), [])

        attr.get_excel_validation()
