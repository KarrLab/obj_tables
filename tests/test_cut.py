""" Test getting children and graph cutting

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-27
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_model import core
import unittest


class Level0(core.Model):
    id = core.SlugAttribute()
    children_01 = core.OneToManyAttribute('Level01', related_name='parent')

    class Meta(core.Model.Meta):
        children = {
            'left': ['children_00'],
            'right': ['children_01'],
            'all': ['children_00', 'children_01'],
        }


class Level00(core.Model):
    id = core.SlugAttribute()
    parent = core.ManyToOneAttribute('Level0', related_name='children_00')

    class Meta(core.Model.Meta):
        children = {
            'left': ['child_000', 'children_001'],
            'all': ['child_000', 'children_001'],
        }


class Level01(core.Model):
    id = core.SlugAttribute()
    child_010 = core.OneToOneAttribute('Level010', related_name='parent')
    child_011 = core.ManyToOneAttribute('Level011', related_name='parents')

    class Meta(core.Model.Meta):
        children = {
            'right': ['child_010', 'child_011'],
            'all': ['child_010', 'child_011'],
        }


class Level000(core.Model):
    id = core.SlugAttribute()
    parents = core.OneToManyAttribute('Level00', related_name='child_000')


class Level001(core.Model):
    id = core.SlugAttribute()
    parents = core.ManyToManyAttribute('Level00', related_name='children_001')


class Level010(core.Model):
    id = core.SlugAttribute()


class Level011(core.Model):
    id = core.SlugAttribute()


class CutTestCase(unittest.TestCase):
    def setUp(self):
        self.obj_0 = Level0(id='obj_0')

        self.obj_00_0 = self.obj_0.children_00.create(id='obj_00_0')
        self.obj_00_1 = self.obj_0.children_00.create(id='obj_00_1')
        self.obj_01_0 = self.obj_0.children_01.create(id='obj_01_0')
        self.obj_01_1 = self.obj_0.children_01.create(id='obj_01_1')

        self.obj_00_0_0 = self.obj_00_0.child_000 = Level000(id='obj_00_0_0')
        self.obj_00_1_0 = self.obj_00_1.children_001.create(id='obj_00_1_0')
        self.obj_00_1_1 = self.obj_00_1.children_001.create(id='obj_00_1_1')
        self.obj_01_0_0 = self.obj_01_0.child_010 = Level010(id='obj_01_0_0')
        self.obj_01_1_0 = self.obj_01_1.child_011 = Level011(id='obj_01_1_0')

    def test_get_immediate_children_kind_none(self):
        self.assertEqual(self.obj_0.get_immediate_children(), self.obj_0.children_01)

        self.assertEqual(self.obj_00_0.get_immediate_children(), [self.obj_00_0.parent])
        self.assertEqual(self.obj_00_1.get_immediate_children(), [self.obj_00_1.parent])
        self.assertEqual(self.obj_01_0.get_immediate_children(), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_1.get_immediate_children(), [self.obj_01_1.child_011])

        self.assertEqual(self.obj_00_0_0.get_immediate_children(), self.obj_00_0_0.parents)
        self.assertEqual(self.obj_00_1_0.get_immediate_children(), self.obj_00_1_0.parents)
        self.assertEqual(self.obj_00_1_1.get_immediate_children(), self.obj_00_1_1.parents)
        self.assertEqual(self.obj_01_0_0.get_immediate_children(), [])
        self.assertEqual(self.obj_01_1_0.get_immediate_children(), [])

    def test_get_immediate_children_kind_all(self):
        self.assertEqual(set(self.obj_0.get_immediate_children(kind='__all__')), set(self.obj_0.children_00) | set(self.obj_0.children_01))

        self.assertEqual(set(self.obj_00_0.get_immediate_children(kind='__all__')), set([self.obj_0, self.obj_00_0_0]))
        self.assertEqual(set(self.obj_00_1.get_immediate_children(kind='__all__')), set([self.obj_0, self.obj_00_1_0, self.obj_00_1_1]))
        self.assertEqual(set(self.obj_01_0.get_immediate_children(kind='__all__')), set([self.obj_0, self.obj_01_0.child_010]))
        self.assertEqual(set(self.obj_01_1.get_immediate_children(kind='__all__')), set([self.obj_0, self.obj_01_1.child_011]))

    def test_get_immediate_children(self):
        self.assertEqual(self.obj_0.get_immediate_children(kind='left'), self.obj_0.children_00)
        self.assertEqual(self.obj_0.get_immediate_children(kind='right'), self.obj_0.children_01)
        self.assertEqual(set(self.obj_0.get_immediate_children(kind='all')), set(self.obj_0.children_00) | set(self.obj_0.children_01))

        self.assertEqual(self.obj_00_0.get_immediate_children(kind='left'), [self.obj_00_0.child_000])
        self.assertEqual(self.obj_00_0.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_00_0.get_immediate_children(kind='all'), [self.obj_00_0.child_000])
        self.assertEqual(self.obj_00_1.get_immediate_children(kind='left'), self.obj_00_1.children_001)
        self.assertEqual(self.obj_00_1.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_00_1.get_immediate_children(kind='all'), self.obj_00_1.children_001)
        self.assertEqual(self.obj_01_0.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_01_0.get_immediate_children(kind='right'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_0.get_immediate_children(kind='all'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_1.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_01_1.get_immediate_children(kind='right'), [self.obj_01_1.child_011])
        self.assertEqual(self.obj_01_1.get_immediate_children(kind='all'), [self.obj_01_1.child_011])

        self.assertEqual(self.obj_00_0_0.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_00_0_0.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_00_0_0.get_immediate_children(kind='all'), [])
        self.assertEqual(self.obj_00_1_0.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_00_1_0.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_00_1_0.get_immediate_children(kind='all'), [])
        self.assertEqual(self.obj_00_1_1.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_00_1_1.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_00_1_1.get_immediate_children(kind='all'), [])
        self.assertEqual(self.obj_01_0_0.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_01_0_0.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_01_0_0.get_immediate_children(kind='all'), [])
        self.assertEqual(self.obj_01_1_0.get_immediate_children(kind='left'), [])
        self.assertEqual(self.obj_01_1_0.get_immediate_children(kind='right'), [])
        self.assertEqual(self.obj_01_1_0.get_immediate_children(kind='all'), [])

    def test_get_immediate_children_filter(self):
        self.assertEqual(self.obj_0.get_immediate_children(kind='all', __type=Level0), [])
        self.assertEqual(set(self.obj_0.get_immediate_children(kind='all', __type=Level00)),
                         set(self.obj_0.children_00))
        self.assertEqual(set(self.obj_0.get_immediate_children(kind='all', __type=Level01)),
                         set(self.obj_0.children_01))

        self.assertEqual(self.obj_0.get_immediate_children(kind='all', id='obj_00_0'),
                         [self.obj_00_0])
        self.assertEqual(self.obj_0.get_immediate_children(kind='all', __type=Level00, id='obj_00_0'),
                         [self.obj_00_0])
        self.assertEqual(self.obj_0.get_immediate_children(kind='all', __type=Level01, id='obj_00_1'),
                         [])

    def test_get_immediate_children_error(self):
        class TestModel(core.Model):
            id = core.SlugAttribute()

            class Meta(core.Model.Meta):
                children = {
                    'all': ['id'],
                }

        model = TestModel(id='model')
        with self.assertRaisesRegex(ValueError, 'not a related attribute'):
            model.get_immediate_children(kind='all')

    def test_get_children_not_recursive(self):
        self.assertEqual(self.obj_0.get_children(recursive=False, kind='left'), self.obj_0.children_00)
        self.assertEqual(self.obj_0.get_children(recursive=False, kind='right'), self.obj_0.children_01)
        self.assertEqual(set(self.obj_0.get_children(recursive=False, kind='all')),
                         set(self.obj_0.children_00) | set(self.obj_0.children_01))

        self.assertEqual(self.obj_00_0.get_children(recursive=False, kind='left'), [self.obj_00_0.child_000])
        self.assertEqual(self.obj_00_0.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_00_0.get_children(recursive=False, kind='all'), [self.obj_00_0.child_000])
        self.assertEqual(self.obj_00_1.get_children(recursive=False, kind='left'), self.obj_00_1.children_001)
        self.assertEqual(self.obj_00_1.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_00_1.get_children(recursive=False, kind='all'), self.obj_00_1.children_001)
        self.assertEqual(self.obj_01_0.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_01_0.get_children(recursive=False, kind='right'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_0.get_children(recursive=False, kind='all'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_1.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_01_1.get_children(recursive=False, kind='right'), [self.obj_01_1.child_011])
        self.assertEqual(self.obj_01_1.get_children(recursive=False, kind='all'), [self.obj_01_1.child_011])

        self.assertEqual(self.obj_00_0_0.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_00_0_0.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_00_0_0.get_children(recursive=False, kind='all'), [])
        self.assertEqual(self.obj_00_1_0.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_00_1_0.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_00_1_0.get_children(recursive=False, kind='all'), [])
        self.assertEqual(self.obj_00_1_1.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_00_1_1.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_00_1_1.get_children(recursive=False, kind='all'), [])
        self.assertEqual(self.obj_01_0_0.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_01_0_0.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_01_0_0.get_children(recursive=False, kind='all'), [])
        self.assertEqual(self.obj_01_1_0.get_children(recursive=False, kind='left'), [])
        self.assertEqual(self.obj_01_1_0.get_children(recursive=False, kind='right'), [])
        self.assertEqual(self.obj_01_1_0.get_children(recursive=False, kind='all'), [])

    def test_get_children(self):
        self.assertEqual(set(self.obj_0.get_children(kind='left')),
                         set(self.obj_0.children_00 + [self.obj_00_0.child_000] + self.obj_00_1.children_001))
        self.assertEqual(set(self.obj_0.get_children(kind='right')),
                         set(self.obj_0.children_01 + [self.obj_01_0.child_010] + [self.obj_01_1.child_011]))
        self.assertEqual(set(self.obj_0.get_children(kind='all')),
                         set(self.obj_0.children_00 + [self.obj_00_0.child_000] + self.obj_00_1.children_001
                             + self.obj_0.children_01 + [self.obj_01_0.child_010] + [self.obj_01_1.child_011]))
        self.assertEqual(set(self.obj_0.get_children(kind='all') + [self.obj_0]), set(self.obj_0.get_related()))

        self.assertEqual(self.obj_00_0.get_children(kind='left'), [self.obj_00_0.child_000])
        self.assertEqual(self.obj_00_0.get_children(kind='right'), [])
        self.assertEqual(self.obj_00_0.get_children(kind='all'), [self.obj_00_0.child_000])
        self.assertEqual(set(self.obj_00_1.get_children(kind='left')), set(self.obj_00_1.children_001))
        self.assertEqual(self.obj_00_1.get_children(kind='right'), [])
        self.assertEqual(set(self.obj_00_1.get_children(kind='all')), set(self.obj_00_1.children_001))
        self.assertEqual(self.obj_01_0.get_children(kind='left'), [])
        self.assertEqual(self.obj_01_0.get_children(kind='right'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_0.get_children(kind='all'), [self.obj_01_0.child_010])
        self.assertEqual(self.obj_01_1.get_children(kind='left'), [])
        self.assertEqual(self.obj_01_1.get_children(kind='right'), [self.obj_01_1.child_011])
        self.assertEqual(self.obj_01_1.get_children(kind='all'), [self.obj_01_1.child_011])

        self.assertEqual(self.obj_00_0_0.get_children(kind='left'), [])
        self.assertEqual(self.obj_00_0_0.get_children(kind='right'), [])
        self.assertEqual(self.obj_00_0_0.get_children(kind='all'), [])
        self.assertEqual(self.obj_00_1_0.get_children(kind='left'), [])
        self.assertEqual(self.obj_00_1_0.get_children(kind='right'), [])
        self.assertEqual(self.obj_00_1_0.get_children(kind='all'), [])
        self.assertEqual(self.obj_00_1_1.get_children(kind='left'), [])
        self.assertEqual(self.obj_00_1_1.get_children(kind='right'), [])
        self.assertEqual(self.obj_00_1_1.get_children(kind='all'), [])
        self.assertEqual(self.obj_01_0_0.get_children(kind='left'), [])
        self.assertEqual(self.obj_01_0_0.get_children(kind='right'), [])
        self.assertEqual(self.obj_01_0_0.get_children(kind='all'), [])
        self.assertEqual(self.obj_01_1_0.get_children(kind='left'), [])
        self.assertEqual(self.obj_01_1_0.get_children(kind='right'), [])
        self.assertEqual(self.obj_01_1_0.get_children(kind='all'), [])

    def test_get_children_filter(self):
        self.assertEqual(set(self.obj_0.get_children(kind='all', __type=Level00)),
                         set(self.obj_0.children_00))
        self.assertEqual(set(self.obj_0.get_children(kind='all', __type=Level01)),
                         set(self.obj_0.children_01))
        self.assertEqual(self.obj_0.get_children(kind='all', id='obj_00_1_0'),
                         [self.obj_00_1_0])
        self.assertEqual(self.obj_0.get_children(kind='all', id='obj_00_1_1'),
                         [self.obj_00_1_1])

    def test_cut_relations(self):
        self.setUp()
        self.obj_0.cut_relations([self.obj_0])
        self.assertEqual(self.obj_0.children_00, [])
        self.assertEqual(self.obj_0.children_01, [])

        self.setUp()
        self.obj_0.cut_relations([self.obj_0] + self.obj_0.children_00)
        self.assertEqual(self.obj_0.children_00, [self.obj_00_0, self.obj_00_1])
        self.assertEqual(self.obj_0.children_01, [])

        self.setUp()
        self.obj_0.cut_relations([self.obj_0] + self.obj_0.children_01)
        self.assertEqual(self.obj_0.children_00, [])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])

        self.setUp()
        self.obj_0.cut_relations([self.obj_0] + self.obj_0.children_00 + self.obj_0.children_01)
        self.assertEqual(self.obj_0.children_00, [self.obj_00_0, self.obj_00_1])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])

        self.setUp()
        self.obj_00_0.cut_relations([self.obj_0])
        self.assertEqual(self.obj_00_0.parent, self.obj_0)

        self.setUp()
        self.obj_00_0.cut_relations([])
        self.assertEqual(self.obj_00_0.parent, None)

        self.setUp()
        self.obj_00_0.cut_relations(self.obj_0.children_00 + self.obj_0.children_01)
        self.assertEqual(self.obj_00_0.parent, None)

        self.setUp()
        self.obj_00_1.cut_relations([self.obj_0])
        self.assertEqual(self.obj_00_1.parent, self.obj_0)

        self.setUp()
        self.obj_00_1.cut_relations([])
        self.assertEqual(self.obj_00_1.parent, None)

        self.setUp()
        self.obj_00_1.cut_relations(self.obj_0.children_00 + self.obj_0.children_01)
        self.assertEqual(self.obj_00_1.parent, None)

        self.setUp()
        self.obj_01_0.cut_relations([self.obj_0])
        self.assertEqual(self.obj_01_0.parent, self.obj_0)

        self.setUp()
        self.obj_01_0.cut_relations([])
        self.assertEqual(self.obj_01_0.parent, None)

        self.setUp()
        self.obj_01_0.cut_relations(self.obj_0.children_00 + self.obj_0.children_01)
        self.assertEqual(self.obj_01_0.parent, None)

        self.setUp()
        self.obj_01_1.cut_relations([self.obj_0])
        self.assertEqual(self.obj_01_1.parent, self.obj_0)

        self.setUp()
        self.obj_01_1.cut_relations([])
        self.assertEqual(self.obj_01_1.parent, None)

        self.setUp()
        self.obj_01_1.cut_relations(self.obj_0.children_00 + self.obj_0.children_01)
        self.assertEqual(self.obj_01_1.parent, None)

    def test_cut(self):
        obj_0 = self.obj_0

        self.setUp()
        self.obj_0.cut(kind='all')
        self.assertTrue(obj_0.is_equal(self.obj_0))

        self.setUp()
        self.obj_0.cut(kind='left')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertNotEqual(self.obj_0.children_00, [])
        self.assertEqual(self.obj_0.children_01, [])

        self.setUp()
        self.obj_0.cut(kind='right')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [])
        self.assertNotEqual(self.obj_0.children_01, [])

        self.setUp()
        self.obj_00_0.cut(kind='left')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_1])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_0.child_000, self.obj_00_0_0)

        self.setUp()
        self.obj_00_0.cut(kind='right')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_1])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_0.child_000, None)

        self.setUp()
        self.obj_00_0.cut(kind='all')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_1])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_0.child_000, self.obj_00_0_0)

        self.setUp()
        self.obj_00_1.cut(kind='left')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_0])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_1.child_000, None)
        self.assertEqual(self.obj_00_1.children_001, [self.obj_00_1_0, self.obj_00_1_1])

        self.setUp()
        self.obj_00_1.cut(kind='right')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_0])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_1.child_000, None)
        self.assertEqual(self.obj_00_1.children_001, [])

        self.setUp()
        self.obj_00_1.cut(kind='all')
        self.assertFalse(obj_0.is_equal(self.obj_0))
        self.assertEqual(self.obj_0.children_00, [self.obj_00_0])
        self.assertEqual(self.obj_0.children_01, [self.obj_01_0, self.obj_01_1])
        self.assertEqual(self.obj_00_1.child_000, None)
        self.assertEqual(self.obj_00_1.children_001, [self.obj_00_1_0, self.obj_00_1_1])

    def test_OneToManyAttribute_cut(self):
        self.setUp()
        cut_children = self.obj_0.children_01.cut(kind='left')
        obj_01_0 = next(c for c in cut_children if c.id == 'obj_01_0')
        obj_01_1 = next(c for c in cut_children if c.id == 'obj_01_1')
        self.assertEqual(obj_01_0.parent, None)
        self.assertEqual(obj_01_1.parent, None)
        self.assertTrue(obj_01_0.is_equal(Level01(id='obj_01_0')))
        self.assertTrue(obj_01_1.is_equal(Level01(id='obj_01_1')))

        self.setUp()
        cut_children = self.obj_0.children_01.cut(kind='right')
        obj_01_0 = next(c for c in cut_children if c.id == 'obj_01_0')
        obj_01_1 = next(c for c in cut_children if c.id == 'obj_01_1')
        self.assertEqual(obj_01_0.parent, None)
        self.assertEqual(obj_01_1.parent, None)
        self.assertEqual(obj_01_0.child_010.id, 'obj_01_0_0')
        self.assertEqual(obj_01_0.child_011, None)
        self.assertEqual(obj_01_1.child_010, None)
        self.assertEqual(obj_01_1.child_011.id, 'obj_01_1_0')

    def test_ManyToOneAttribute_cut(self):
        self.setUp()
        cut_children = self.obj_0.children_00.cut(kind='left')
        obj_00_0 = next(c for c in cut_children if c.id == 'obj_00_0')
        obj_00_1 = next(c for c in cut_children if c.id == 'obj_00_1')
        self.assertEqual(obj_00_0.parent, None)
        self.assertEqual(obj_00_1.parent, None)
        self.assertEqual(obj_00_0.child_000.id, 'obj_00_0_0')
        self.assertEqual(obj_00_0.children_001, [])
        self.assertEqual(obj_00_1.child_000, None)
        self.assertEqual(set(c.id for c in obj_00_1.children_001), set(['obj_00_1_0', 'obj_00_1_1']))

        self.setUp()
        cut_children = self.obj_0.children_00.cut(kind='right')
        obj_00_0 = next(c for c in cut_children if c.id == 'obj_00_0')
        obj_00_1 = next(c for c in cut_children if c.id == 'obj_00_1')
        self.assertEqual(obj_00_0.parent, None)
        self.assertEqual(obj_00_1.parent, None)
        self.assertTrue(obj_00_0.is_equal(Level00(id='obj_00_0')))
        self.assertTrue(obj_00_1.is_equal(Level00(id='obj_00_1')))

    def test_ManyToManyAttribute_cut(self):
        self.setUp()
        cut_children = self.obj_00_1.children_001.cut(kind='all')
        self.assertEqual(len(cut_children), 2)
        obj_00_1_0 = next(c for c in cut_children if c.id == 'obj_00_1_0')
        obj_00_1_1 = next(c for c in cut_children if c.id == 'obj_00_1_1')
        self.assertTrue(obj_00_1_0.is_equal(Level001(id='obj_00_1_0')))
        self.assertTrue(obj_00_1_1.is_equal(Level001(id='obj_00_1_1')))

        self.setUp()
        cut_children = self.obj_00_1_0.parents.cut(kind='left')
        self.assertEqual(len(cut_children), 1)
        self.assertTrue(cut_children[0].is_equal(Level00(id='obj_00_1', children_001=[
                        Level001(id='obj_00_1_0'), Level001(id='obj_00_1_1')])))

        self.setUp()
        cut_children = self.obj_00_1_0.parents.cut(kind='right')
        self.assertEqual(len(cut_children), 1)
        self.assertTrue(cut_children[0].is_equal(Level00(id='obj_00_1')))

        self.setUp()
        cut_children = self.obj_00_1_0.parents.cut(kind='all')
        self.assertEqual(len(cut_children), 1)
        self.assertTrue(cut_children[0].is_equal(Level00(id='obj_00_1', children_001=[
                        Level001(id='obj_00_1_0'), Level001(id='obj_00_1_1')])))
