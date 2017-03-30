""" Data model to represent models.

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from datetime import date, time, datetime
from enum import Enum
from itertools import chain
from obj_model import core
from obj_model.core import excel_col_name
import re
import resource
import sys
import unittest


class Order(Enum):
    root = 1
    leaf = 2


class Root(core.Model):
    label = core.StringAttribute(verbose_name='Label', max_length=255, primary=True, unique=True)

    class Meta(core.Model.Meta):
        pass


class Leaf(core.Model):
    root = core.ManyToOneAttribute(Root, verbose_name='Root',
                                   related_name='leaves', verbose_related_name='Leaves', none=False)
    id = core.RegexAttribute(verbose_name='ID', min_length=1, max_length=63,
                             pattern=r'^[a-z][a-z0-9_]*$', flags=re.I, primary=True)
    name = core.StringAttribute(verbose_name='Name', max_length=255)

    class Meta(core.Model.Meta):
        verbose_name = 'Leaf'
        verbose_name_plural = 'Leaves'
        attribute_order = ('id', )


class UnrootedLeaf(Leaf):
    name = core.StringAttribute(verbose_name='Name', max_length=10)

    root2 = core.ManyToOneAttribute(Root, none=True, verbose_name='Root', related_name='leaves2')
    id2 = core.RegexAttribute(verbose_name='ID', min_length=1, max_length=63,
                              pattern=r'^[a-z][a-z0-9_]*$', flags=re.I)
    name2 = core.StringAttribute(verbose_name='Name', min_length=2, max_length=3)
    float2 = core.FloatAttribute(verbose_name='Float', min=2., max=3.)
    float3 = core.FloatAttribute(verbose_name='Float', min=2., nan=False)
    enum2 = core.EnumAttribute(Order, verbose_name='Enum')
    enum3 = core.EnumAttribute(Order, verbose_name='Enum', default=Order['leaf'])
    multi_word_name = core.StringAttribute()


class Leaf3(UnrootedLeaf):

    class Meta(core.Model.Meta):
        attribute_order = ('id2', 'name2', )


class Grandparent(core.Model):
    id = core.StringAttribute(max_length=1, primary=True, unique=True)
    val = core.StringAttribute()


class Parent(core.Model):
    id = core.StringAttribute(max_length=2, primary=True, unique=True)
    val = core.StringAttribute()
    grandparent = core.ManyToOneAttribute(Grandparent, related_name='children', none=False)


class Child(core.Model):
    id = core.StringAttribute(primary=True)
    val = core.StringAttribute()
    parent = core.ManyToOneAttribute(Parent, related_name='children', none=False)


class UniqueRoot(Root):
    label = core.SlugAttribute(verbose_name='Label')
    url = core.UrlAttribute()
    int_attr = core.IntegerAttribute()
    pos_int_attr = core.PositiveIntegerAttribute()

    class Meta(core.Model.Meta):
        pass


class DateRoot(core.Model):
    date = core.DateAttribute(none=True)
    time = core.TimeAttribute(none=True)
    datetime = core.DateTimeAttribute(none=True)


class NotNoneDateRoot(core.Model):
    date = core.DateAttribute(none=False)
    time = core.TimeAttribute(none=False)
    datetime = core.DateTimeAttribute(none=False)


class OneToOneRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class OneToOneLeaf(core.Model):
    root = core.OneToOneAttribute(OneToOneRoot, related_name='leaf', none=False)


class ManyToOneRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class ManyToOneLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    root = core.ManyToOneAttribute(ManyToOneRoot, related_name='leaves', none=False)


class OneToManyRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class OneToManyLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    roots = core.OneToManyAttribute(OneToManyRoot, related_name='leaf', related_none=False)


class ManyToManyRoot(core.Model):
    id = core.SlugAttribute(verbose_name='ID')


class ManyToManyLeaf(core.Model):
    id = core.SlugAttribute(verbose_name='ID')
    roots = core.ManyToManyAttribute(ManyToManyRoot, related_name='leaves')


class UniqueTogetherRoot(core.Model):
    val0 = core.StringAttribute(unique=True)
    val1 = core.StringAttribute(unique=False)
    val2 = core.StringAttribute(unique=False)

    class Meta(core.Model.Meta):
        unique_together = (('val1', 'val2'),)


class InlineRoot(core.Model):

    class Meta(core.Model.Meta):
        tabular_orientation = core.TabularOrientation.inline


class TestCore(unittest.TestCase):

    def test_get_models(self):
        models = set((
            Root, Leaf, UnrootedLeaf, Leaf3, Grandparent, Parent, Child,
            UniqueRoot, DateRoot, NotNoneDateRoot, OneToOneRoot, OneToOneLeaf,
            ManyToOneRoot, ManyToOneLeaf, OneToManyRoot, OneToManyLeaf, ManyToManyRoot, ManyToManyLeaf,
            UniqueTogetherRoot, InlineRoot
        ))
        self.assertEqual(set(core.get_models(module=sys.modules[__name__])), models)
        self.assertEqual(models.difference(core.get_models()), set())

        models.remove(InlineRoot)
        self.assertEqual(set(core.get_models(module=sys.modules[__name__], inline=False)), models)
        self.assertEqual(models.difference(core.get_models(inline=False)), set())

    def test_get_model(self):
        self.assertEqual(core.get_model('Root'), None)
        self.assertEqual(core.get_model('Root', module=sys.modules[__name__]), Root)
        self.assertEqual(core.get_model(Root.__module__ + '.Root'), Root)

    def test_verbose_name(self):
        self.assertEqual(Root.Meta.verbose_name, 'Root')
        self.assertEqual(Root.Meta.verbose_name_plural, 'Roots')

        self.assertEqual(Leaf.Meta.verbose_name, 'Leaf')
        self.assertEqual(Leaf.Meta.verbose_name_plural, 'Leaves')

        self.assertEqual(UnrootedLeaf.Meta.verbose_name, 'Unrooted leaf')
        self.assertEqual(UnrootedLeaf.Meta.verbose_name_plural, 'Unrooted leaves')

        self.assertEqual(Leaf3.Meta.verbose_name, 'Leaf3')
        self.assertEqual(Leaf3.Meta.verbose_name_plural, 'Leaf3s')

        self.assertEqual(UnrootedLeaf.Meta.attributes['multi_word_name'].verbose_name, 'Multi word name')

    def test_meta_attributes(self):
        self.assertEqual(set(Root.Meta.attributes.keys()), set(('label', )))
        self.assertEqual(set(Leaf.Meta.attributes.keys()), set(('root', 'id', 'name', )))

    def test_meta_related_attributes(self):
        self.assertEqual(set(Root.Meta.related_attributes.keys()), set(('leaves', 'leaves2', )))
        self.assertEqual(set(Leaf.Meta.related_attributes.keys()), set())

    def test_attributes(self):
        root = Root()
        leaf = Leaf()

        self.assertEqual(set(vars(root).keys()), set(('_source', 'label', 'leaves', 'leaves2')))
        self.assertEqual(set(vars(leaf).keys()), set(('_source', 'root', 'id', 'name')))

    def test_attribute_order(self):
        self.assertEqual(set(Root.Meta.attribute_order), set(Root.Meta.attributes.keys()))
        self.assertEqual(set(Leaf.Meta.attribute_order), set(Leaf.Meta.attributes.keys()))
        self.assertEqual(set(UnrootedLeaf.Meta.attribute_order), set(UnrootedLeaf.Meta.attributes.keys()))
        self.assertEqual(set(Leaf3.Meta.attribute_order), set(Leaf3.Meta.attributes.keys()))

        self.assertEqual(Root.Meta.attribute_order, ('label', ))
        self.assertEqual(Leaf.Meta.attribute_order, ('id', 'name', 'root'))
        self.assertEqual(UnrootedLeaf.Meta.attribute_order, (
            'id', 'name', 'root',
            'enum2', 'enum3', 'float2', 'float3', 'id2', 'multi_word_name', 'name2', 'root2', ))
        self.assertEqual(Leaf3.Meta.attribute_order, (
            'id2', 'name2',
            'enum2', 'enum3', 'float2', 'float3', 'id', 'multi_word_name', 'name', 'root', 'root2', ))

    def test_set(self):
        leaf = Leaf(id='leaf_1', name='Leaf 1')
        self.assertEqual(leaf.id, 'leaf_1')
        self.assertEqual(leaf.name, 'Leaf 1')

        leaf.id = 'leaf_2'
        leaf.name = 'Leaf 2'
        self.assertEqual(leaf.id, 'leaf_2')
        self.assertEqual(leaf.name, 'Leaf 2')

    def test_memory_use(self):
        ''' Not a test; rather a measurement of the memory use by schema objects for monitoring '''
        root = Root(label='root')
        n = 100
        iter = 0
        n_leaves = 0
        while n <= 10000:
            start_RAM = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            for i in range(n):
                Leaf(root=root, id=str(i), name="leaf_{}_{}".format(iter, i))
            print("{} {} objects: {} KB/obj".format(n, 'Leaf',
                                                    (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - start_RAM) / n))
            n_leaves += n
            self.assertEqual(len(set(root.leaves)), n_leaves)
            iter += 1
            n *= 4

    def test_set_related(self):
        root1 = Root(label='root1')
        root2 = Root(label='root2')

        leaf1 = Leaf(id='leaf1')
        leaf2 = Leaf(id='leaf2')
        leaf3 = Leaf(id='leaf3')
        self.assertEqual(leaf1.root, None)
        self.assertEqual(leaf2.root, None)
        self.assertEqual(leaf3.root, None)

        leaf1.root = root1
        leaf2.root = root1
        leaf3.root = root2
        self.assertEqual(leaf1.root, root1)
        self.assertEqual(leaf2.root, root1)
        self.assertEqual(leaf3.root, root2)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf2)))
        self.assertEqual(root2.leaves, [leaf3])

        leaf2.root = root2
        leaf3.root = root1
        self.assertEqual(leaf1.root, root1)
        self.assertEqual(leaf2.root, root2)
        self.assertEqual(leaf3.root, root1)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf3, )))
        self.assertEqual(root2.leaves, [leaf2])

        leaf4 = Leaf(root=root1)
        self.assertEqual(leaf4.root, root1)
        self.assertEqual(set(root1.leaves), set((leaf1, leaf3, leaf4)))

    def test_get_related(self):
        g0 = Grandparent(id='root-0')
        p0 = [
            Parent(grandparent=g0, id='node-0-0'),
            Parent(grandparent=g0, id='node-0-1'),
        ]
        c0 = [
            Child(parent=p0[0], id='leaf-0-0-0'),
            Child(parent=p0[0], id='leaf-0-0-1'),
            Child(parent=p0[1], id='leaf-0-1-0'),
            Child(parent=p0[1], id='leaf-0-1-1'),
        ]

        g1 = Grandparent(id='root-1')
        p1 = [
            Parent(grandparent=g1, id='node-1-0'),
            Parent(grandparent=g1, id='node-1-1'),
        ]
        c1 = [
            Child(parent=p1[0], id='leaf-1-0-0'),
            Child(parent=p1[0], id='leaf-1-0-1'),
            Child(parent=p1[1], id='leaf-1-1-0'),
            Child(parent=p1[1], id='leaf-1-1-1'),
        ]

        self.assertEqual(set(g0.get_related()), set((g0,)) | set(p0) | set(c0))
        self.assertEqual(set(p0[0].get_related()), set((g0,)) | set(p0) | set(c0))
        self.assertEqual(set(c0[0].get_related()), set((g0,)) | set(p0) | set(c0))

        self.assertEqual(set(g1.get_related()), set((g1,)) | set(p1) | set(c1))
        self.assertEqual(set(p1[0].get_related()), set((g1,)) | set(p1) | set(c1))
        self.assertEqual(set(c1[0].get_related()), set((g1,)) | set(p1) | set(c1))

    def test_equal(self):
        root1 = Root(label='a')
        root2 = Root(label='b')

        leaf1 = Leaf(root=root1, id='a', name='ab')
        leaf2 = Leaf(root=root1, id='a', name='ab')
        leaf3 = Leaf(root=root1, id='b', name='ab')
        leaf4 = Leaf(root=root2, id='b', name='ab')

        self.assertFalse(leaf1 is leaf2)
        self.assertFalse(leaf1 is leaf3)
        self.assertFalse(leaf2 is leaf3)

        self.assertTrue(leaf1.is_equal(leaf2))
        self.assertFalse(leaf1.is_equal(leaf3))
        self.assertFalse(leaf3.is_equal(leaf4))

    def test_hash(self):
        self.assertEqual(len([Root()]), 1)
        self.assertEqual(len([Leaf(), Leaf()]), 2)
        self.assertEqual(len([UnrootedLeaf(), UnrootedLeaf()]), 2)
        self.assertEqual(len([Leaf3(), Leaf3(), Leaf3()]), 3)

    def test___str__(self):
        root = Root(label='test label')
        self.assertEqual(str(root), '<{}.{}: {}>'.format(Root.__module__, 'Root', root.label))

    def test_validate_attribute(self):
        root = Root()
        root.clean()
        self.assertIn('value for primary attribute cannot be empty',
                      root.validate().attributes[0].messages[0])

        leaf = Leaf()
        self.assertEqual(set((x.attribute.name for x in leaf.validate().attributes)), set(('id', 'root',)))

        leaf.id = 'a'
        self.assertEqual(set((x.attribute.name for x in leaf.validate().attributes)), set(('root',)))

        leaf.name = 1
        self.assertEqual(set((x.attribute.name for x in leaf.validate().attributes)), set(('name', 'root',)))

        leaf.name = 'b'
        self.assertEqual(set((x.attribute.name for x in leaf.validate().attributes)), set(('root',)))

        leaf.root = root
        self.assertEqual(leaf.validate(), None)
        self.assertIn('value for primary attribute cannot be empty',
                      root.validate().attributes[0].messages[0])

        unrooted_leaf = UnrootedLeaf(root=root, id='a', id2='b', name2='ab', float2=2.4,
                                     float3=2.4, enum2=Order['root'], enum3=Order['leaf'])
        self.assertEqual(unrooted_leaf.validate(), None)

    def test_validate_string_attribute(self):
        leaf = UnrootedLeaf()

        leaf.name2 = 'a'
        self.assertIn('name2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.name2 = 'abcd'
        self.assertIn('name2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.name2 = 'ab'
        self.assertNotIn('name2', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_regex_attribute(self):
        leaf = Leaf()

        leaf.id = ''
        self.assertIn('id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = '1'
        self.assertIn('id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = 'a-'
        self.assertIn('id', [x.attribute.name for x in leaf.validate().attributes])

        leaf.id = 'a_'
        self.assertNotIn('id', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_slug_attribute(self):
        root = UniqueRoot(label='root-0')
        self.assertIn('label', [x.attribute.name for x in root.validate().attributes])

        root.label = 'root_0'
        self.assertEqual(root.validate(), None)

    def test_validate_url_attribute(self):
        root = UniqueRoot(url='root-0')
        self.assertIn('url', [x.attribute.name for x in root.validate().attributes])

        root.url = 'http://www.test.com'
        self.assertNotIn('url', [x.attribute.name for x in root.validate().attributes])

    def test_validate_float_attribute(self):
        leaf = UnrootedLeaf()

        # max=3.
        leaf.float2 = 'a'
        leaf.clean()
        self.assertIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 1
        leaf.clean()
        self.assertIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 4
        leaf.clean()
        self.assertIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 3
        leaf.clean()
        self.assertNotIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 3.
        leaf.clean()
        self.assertNotIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 2.
        leaf.clean()
        self.assertNotIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = 2.5
        leaf.clean()
        self.assertNotIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float2 = float('nan')
        leaf.clean()
        self.assertNotIn('float2', [x.attribute.name for x in leaf.validate().attributes])

        # max=nan
        leaf.float3 = 2.5
        leaf.clean()
        self.assertNotIn('float3', [x.attribute.name for x in leaf.validate().attributes])

        leaf.float3 = float('nan')
        leaf.clean()
        self.assertIn('float3', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_int_attribute(self):
        root = UniqueRoot(int_attr='1.0.')
        root.clean()
        self.assertIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = '1.5'
        root.clean()
        self.assertIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1.5
        root.clean()
        self.assertIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = '1.'
        root.clean()
        self.assertNotIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1.
        root.clean()
        self.assertNotIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = 1
        root.clean()
        self.assertNotIn('int_attr', [x.attribute.name for x in root.validate().attributes])

        root.int_attr = None
        root.clean()
        self.assertNotIn('int_attr', [x.attribute.name for x in root.validate().attributes])

    def test_validate_pos_int_attribute(self):
        root = UniqueRoot(pos_int_attr='0.')
        root.clean()
        self.assertIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1.5
        root.clean()
        self.assertIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = -1
        root.clean()
        self.assertIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 0
        root.clean()
        self.assertIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1.
        root.clean()
        self.assertNotIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = 1
        root.clean()
        self.assertNotIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

        root.pos_int_attr = None
        root.clean()
        self.assertNotIn('pos_int_attr', [x.attribute.name for x in root.validate().attributes])

    def test_validate_enum_attribute(self):
        leaf = UnrootedLeaf()
        leaf.clean()

        self.assertIn('enum2', [x.attribute.name for x in leaf.validate().attributes])
        self.assertNotIn('enum3', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = Order['root']
        leaf.clean()
        self.assertNotIn('enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 'root'
        leaf.clean()
        self.assertNotIn('enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 1
        leaf.clean()
        self.assertNotIn('enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 'root2'
        leaf.clean()
        self.assertIn('enum2', [x.attribute.name for x in leaf.validate().attributes])

        leaf.enum2 = 3
        leaf.clean()
        self.assertIn('enum2', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_date_attribute(self):
        root = DateRoot()

        # positive examples
        root.date = date(2000, 10, 1)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = '1900-1-1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = 1
        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = 1.
        root.clean()
        self.assertEqual(root.validate(), None)

        # negative examples
        root.date = date(1, 10, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = datetime(1, 10, 1, 1, 0, 0, 0)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = '1900-1-1 1:00:00.00'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = 0
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.date = 1.5
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.date = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    def test_time_attribute(self):
        root = DateRoot()

        # positive examples
        root.time = time(1, 0, 0, 0)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = '1:1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = '1:1:1'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = 0.25
        root.clean()
        self.assertEqual(root.validate(), None)

        # negative examples
        root.time = time(1, 0, 0, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = '1:1:1.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = '1900-01-01 1:1:1.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = -0.25
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.time = 1.25
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.time = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    def test_datetime_attribute(self):
        root = DateRoot()

        # positive examples
        root.datetime = None
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = datetime(2000, 10, 1, 0, 0, 1, 0)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = date(2000, 10, 1)
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = '2000-10-01'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = '2000-10-01 1:00:00'
        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = 10.25
        root.clean()
        self.assertEqual(root.validate(), None)

        # negative examples
        root.datetime = datetime(2000, 10, 1, 0, 0, 1, 1)
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.datetime = '2000-10-01 1:00:00.01'
        root.clean()
        self.assertNotEqual(root.validate(), None)

        root.datetime = -1.5
        root.clean()
        self.assertNotEqual(root.validate(), None)

        # Not none
        root = NotNoneDateRoot()
        root.date = date(1900, 1, 1)
        root.time = time(0, 0, 0, 0)
        root.datetime = datetime(1900, 1, 1, 0, 0, 0, 0)

        root.clean()
        self.assertEqual(root.validate(), None)

        root.datetime = None
        root.clean()
        self.assertNotEqual(root.validate(), None)

    @unittest.expectedFailure
    def test_related_no_double_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(RootDefault, related_name='leaf',
                                          default=lambda: RootDefault(label='root0'),
                                          related_default=lambda: LeafDefault(label='leaf0'))

    def test_onetoone_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(RootDefault, related_name='leaf', default=lambda: RootDefault(label='root2'))

        leaf0 = LeafDefault(root=RootDefault())
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertIsInstance(leaf0.root, RootDefault)
        self.assertEqual(leaf0.root.label, 'root0')
        self.assertEqual(leaf0.root.leaf, leaf0)

        leaf1 = LeafDefault(label='leaf1')
        self.assertEqual(leaf1.label, 'leaf1')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root2')
        self.assertEqual(leaf1.root.leaf, leaf1)

        leaf2 = LeafDefault(label='leaf2', root=RootDefault(label='root3'))
        self.assertEqual(leaf2.label, 'leaf2')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root3')
        self.assertEqual(leaf2.root.leaf, leaf2)

    def test_onetoone_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf0')
            root = core.OneToOneAttribute(RootDefault, related_name='leaf',
                                          related_default=lambda: LeafDefault(label='leaf2'))

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertEqual(leaf0.root, None)

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertIsInstance(root0.leaf, LeafDefault)
        self.assertEqual(root0.leaf.label, 'leaf2')
        self.assertEqual(root0.leaf.root, root0)

        root1 = RootDefault(label='root1')
        self.assertEqual(root1.label, 'root1')
        self.assertIsInstance(root1.leaf, LeafDefault)
        self.assertEqual(root1.leaf.label, 'leaf2')
        self.assertEqual(root1.leaf.root, root1)

        root2 = RootDefault(label='root2', leaf=LeafDefault(label='leaf3'))
        self.assertEqual(root2.label, 'root2')
        self.assertIsInstance(root2.leaf, LeafDefault)
        self.assertEqual(root2.leaf.label, 'leaf3')
        self.assertEqual(root2.leaf.root, root2)

    def test_onetomany_default(self):
        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf22')

        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')
            leaves = core.OneToManyAttribute(LeafDefault, related_name='root', default=lambda: [
                LeafDefault(label='leaf00'), LeafDefault(label='leaf01')])

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(len(root0.leaves), 2)
        self.assertEqual(set([l.label for l in root0.leaves]), set(['leaf00', 'leaf01']))
        self.assertEqual(set([l.root for l in root0.leaves]), set([root0]))

        root1 = RootDefault(leaves=[LeafDefault(), LeafDefault()])
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(len(root1.leaves), 2)
        self.assertEqual(set([l.label for l in root1.leaves]), set(['leaf22', 'leaf22']))
        self.assertEqual(set([l.root for l in root1.leaves]), set([root1]))

        root2 = RootDefault(label='root2', leaves=[LeafDefault(label='leaf20'), LeafDefault(label='leaf21')])
        self.assertEqual(root2.label, 'root2')
        self.assertEqual(len(root2.leaves), 2)
        self.assertEqual(set([l.label for l in root2.leaves]), set(['leaf20', 'leaf21']))
        self.assertEqual(set([l.root for l in root2.leaves]), set([root2]))

    def test_onetomany_related_default(self):
        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf22')

        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')
            leaves = core.OneToManyAttribute(LeafDefault, related_name='root',
                                             related_default=lambda: RootDefault(label='root1'))

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(root0.leaves, [])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf22')
        self.assertIsInstance(leaf0.root, RootDefault)
        self.assertEqual(leaf0.root.label, 'root1')
        self.assertEqual(len(leaf0.root.leaves), 1)
        self.assertEqual(leaf0.root.leaves[0], leaf0)

        leaf1 = LeafDefault(label='leaf33')
        self.assertEqual(leaf1.label, 'leaf33')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root1')
        self.assertEqual(len(leaf1.root.leaves), 1)
        self.assertEqual(leaf1.root.leaves[0], leaf1)

        leaf2 = LeafDefault(label='leaf44', root=RootDefault(label='root2'))
        self.assertEqual(leaf2.label, 'leaf44')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root2')
        self.assertEqual(len(leaf2.root.leaves), 1)
        self.assertEqual(leaf2.root.leaves[0], leaf2)

    def test_manytoone_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf2')
            root = core.ManyToOneAttribute(RootDefault, related_name='leaves',
                                           default=lambda: RootDefault(label='root1'))

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(len(root0.leaves), 0)

        leaf1 = LeafDefault()
        self.assertEqual(leaf1.label, 'leaf2')
        self.assertIsInstance(leaf1.root, RootDefault)
        self.assertEqual(leaf1.root.label, 'root1')
        self.assertEqual(leaf1.root.leaves, [leaf1])

        leaf2 = LeafDefault(label='leaf4', root=RootDefault(label='root3'))
        self.assertEqual(leaf2.label, 'leaf4')
        self.assertIsInstance(leaf2.root, RootDefault)
        self.assertEqual(leaf2.root.label, 'root3')
        self.assertEqual(leaf2.root.leaves, [leaf2])

    def test_manytoone_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf2')
            root = core.ManyToOneAttribute(RootDefault, related_name='leaves',
                                           related_default=lambda: [LeafDefault(label='leaf3'), LeafDefault(label='leaf4'), LeafDefault(label='leaf5')])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf2')
        self.assertEqual(leaf0.root, None)

        root1 = RootDefault()
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(set([l.__class__ for l in root1.leaves]), set([LeafDefault]))
        self.assertEqual(set([l.label for l in root1.leaves]), set(['leaf3', 'leaf4', 'leaf5']))
        self.assertEqual(set([l.root for l in root1.leaves]), set([root1]))

        root2 = RootDefault(label='root2', leaves=[LeafDefault(label='leaf6'), LeafDefault(label='leaf7')])
        self.assertEqual(root2.label, 'root2')
        self.assertEqual(set([l.__class__ for l in root2.leaves]), set([LeafDefault]))
        self.assertEqual(set([l.label for l in root2.leaves]), set(['leaf6', 'leaf7']))
        self.assertEqual(set([l.root for l in root2.leaves]), set([root2]))

    def test_manytomany_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf0')
            roots = core.ManyToManyAttribute(RootDefault, related_name='leaves', default=lambda: [
                                             RootDefault(label='root1'), RootDefault(label='root2')])

        root0 = RootDefault()
        self.assertEqual(root0.label, 'root0')
        self.assertEqual(root0.leaves, [])

        leaf1 = LeafDefault()
        self.assertEqual(leaf1.label, 'leaf0')
        self.assertEqual(len(leaf1.roots), 2)
        self.assertEqual(set([r.__class__ for r in leaf1.roots]), set([RootDefault]))
        self.assertEqual(set([r.label for r in leaf1.roots]), set(['root1', 'root2']))
        self.assertEqual(set([len(r.leaves) for r in leaf1.roots]), set([1]))
        self.assertEqual(set([r.leaves[0] for r in leaf1.roots]), set([leaf1]))

    def test_manytomany_related_default(self):
        class RootDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='root0')

        class LeafDefault(core.Model):
            label = core.StringAttribute(primary=True, unique=True, default='leaf0')
            roots = core.ManyToManyAttribute(RootDefault, related_name='leaves', related_default=lambda: [
                                             LeafDefault(label='leaf1'), LeafDefault(label='leaf2'), LeafDefault(label='leaf3')])

        leaf0 = LeafDefault()
        self.assertEqual(leaf0.label, 'leaf0')
        self.assertEqual(leaf0.roots, [])

        root1 = RootDefault()
        self.assertEqual(root1.label, 'root0')
        self.assertEqual(len(root1.leaves), 3)
        self.assertEqual(set([l.__class__ for l in root1.leaves]), set([LeafDefault]))
        self.assertEqual(set([l.label for l in root1.leaves]), set(['leaf1', 'leaf2', 'leaf3']))
        self.assertEqual(set([len(l.roots) for l in root1.leaves]), set([1]))
        self.assertEqual(set([l.roots[0] for l in root1.leaves]), set([root1]))

    def test_validate_onetoone_attribute(self):
        root = OneToOneRoot(id='root')
        leaf = OneToOneLeaf(root=root)

        self.assertEqual(root.leaf, leaf)

        self.assertEqual(root.validate(), None)
        self.assertEqual(leaf.validate(), None)

    def test_validate_manytoone_attribute(self):
        # none=False
        leaf = Leaf()
        self.assertIn('root', [x.attribute.name for x in leaf.validate().attributes])

        def set_root():
            leaf.root = Leaf()
        self.assertRaises(AttributeError, set_root)

        leaf.root = Root()
        self.assertNotIn('root', [x.attribute.name for x in leaf.validate().attributes])

        # none=True
        unrooted_leaf = UnrootedLeaf()
        self.assertNotIn('root2', [x.attribute.name for x in unrooted_leaf.validate().attributes])

    def test_validate_onetomany_attribute(self):
        root = OneToManyRoot()
        leaf = OneToManyLeaf()
        self.assertNotIn('roots', [x.attribute.name for x in leaf.validate().attributes])

        root.leaf = leaf
        self.assertEqual(leaf.roots, [root])
        self.assertNotIn('leaf', [x.attribute.name for x in root.validate().attributes])
        self.assertNotIn('roots', [x.attribute.name for x in leaf.validate().attributes])

    def test_validate_manytomany_attribute(self):
        roots = [
            ManyToManyRoot(id='root_0'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_2'),
            ManyToManyRoot(id='root_3'),
        ]
        leaves = [
            ManyToManyLeaf(roots=roots[0:2], id='leaf_0'),
            ManyToManyLeaf(roots=roots[1:3], id='leaf_1'),
            ManyToManyLeaf(roots=roots[2:4], id='leaf_2'),
        ]

        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))
        self.assertEqual(set(roots[2].leaves), set(leaves[1:3]))
        self.assertEqual(roots[3].leaves, leaves[2:3])

        # self.assertRaises(Exception, lambda: leaves[0].roots.add(roots[2]))

        for obj in chain(roots, leaves):
            error = obj.validate()
            self.assertEqual(error, None)

    def test_onetoone_set_related(self):
        root = OneToOneRoot()
        leaf = OneToOneLeaf()

        root.leaf = leaf
        self.assertEqual(leaf.root, root)

        root.leaf = None
        self.assertEqual(leaf.root, None)

        leaf.root = root
        self.assertEqual(root.leaf, leaf)

        leaf.root = None
        self.assertEqual(root.leaf, None)

    def test_manytoone_set_related(self):
        roots = [
            ManyToOneRoot(id='root0'),
            ManyToOneRoot(id='root1'),
        ]
        leaves = [
            ManyToOneLeaf(id='leaf0'),
            ManyToOneLeaf(id='leaf1'),
        ]

        leaves[0].root = roots[0]
        self.assertEqual(roots[0].leaves, leaves[0:1])

        leaves[1].root = roots[0]
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))

        leaves[0].root = None
        self.assertEqual(roots[0].leaves, leaves[1:2])

        roots[0].leaves = []
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(leaves[1].root, None)

        roots[0].leaves.add(leaves[0])
        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(leaves[0].root, roots[0])

        roots[0].leaves.update(leaves[1:2])
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))
        self.assertEqual(leaves[1].root, roots[0])

        roots[0].leaves.remove(leaves[0])
        self.assertEqual(roots[0].leaves, leaves[1:2])
        self.assertEqual(leaves[0].root, None)

        roots[0].leaves = []
        leaves[0].root = roots[0]
        leaves[0].root = roots[1]
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(roots[1].leaves, leaves[0:1])

        roots[0].leaves = leaves[0:1]
        self.assertEqual(roots[0].leaves, leaves[0:1])
        self.assertEqual(roots[1].leaves, [])
        self.assertEqual(leaves[0].root, roots[0])

        roots[1].leaves = leaves[0:2]
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))
        self.assertEqual(leaves[0].root, roots[1])
        self.assertEqual(leaves[1].root, roots[1])

    def test_onetomany_set_related(self):
        roots = [
            OneToManyRoot(id='root0'),
            OneToManyRoot(id='root1'),
        ]
        leaves = [
            OneToManyLeaf(id='leaf0'),
            OneToManyLeaf(id='leaf1'),
        ]

        roots[0].leaf = leaves[0]
        self.assertEqual(leaves[0].roots, roots[0:1])

        roots[1].leaf = leaves[0]
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))

        roots[0].leaf = None
        self.assertEqual(leaves[0].roots, roots[1:2])

        leaves[0].roots = []
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(roots[1].leaf, None)

        leaves[0].roots.add(roots[0])
        self.assertEqual(leaves[0].roots, roots[0:1])
        self.assertEqual(roots[0].leaf, leaves[0])

        leaves[0].roots.update(roots[1:2])
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))
        self.assertEqual(roots[1].leaf, leaves[0])

        leaves[0].roots.remove(roots[0])
        self.assertEqual(leaves[0].roots, roots[1:2])
        self.assertEqual(roots[0].leaf, None)

        leaves[0].roots = []
        roots[0].leaf = leaves[0]
        roots[0].leaf = leaves[1]
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(leaves[1].roots, roots[0:1])

        leaves[0].roots = roots[0:1]
        self.assertEqual(leaves[0].roots, roots[0:1])
        self.assertEqual(leaves[1].roots, [])
        self.assertEqual(roots[0].leaf, leaves[0])

        leaves[1].roots = roots[0:2]
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(set(leaves[1].roots), set(roots[0:2]))
        self.assertEqual(roots[0].leaf, leaves[1])
        self.assertEqual(roots[1].leaf, leaves[1])

    def test_manytomany_set_related(self):
        roots = [
            ManyToManyRoot(id='root0'),
            ManyToManyRoot(id='root1'),
        ]
        leaves = [
            ManyToManyLeaf(id='leaf0'),
            ManyToManyLeaf(id='leaf1'),
        ]

        roots[0].leaves.add(leaves[0])
        self.assertEqual(leaves[0].roots, roots[0:1])

        roots[0].leaves.remove(leaves[0])
        self.assertEqual(leaves[0].roots, [])

        roots[0].leaves.add(leaves[0])
        roots[1].leaves.add(leaves[0])
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))

        roots[0].leaves.clear()
        roots[1].leaves.clear()
        self.assertEqual(leaves[0].roots, [])
        self.assertEqual(leaves[1].roots, [])

        roots[0].leaves = leaves
        roots[1].leaves = leaves
        self.assertEqual(set(leaves[0].roots), set(roots[0:2]))
        self.assertEqual(set(leaves[1].roots), set(roots[0:2]))

        # reverse
        roots[0].leaves.clear()
        roots[1].leaves.clear()

        leaves[0].roots.add(roots[0])
        self.assertEqual(roots[0].leaves, leaves[0:1])

        leaves[0].roots.remove(roots[0])
        self.assertEqual(roots[0].leaves, [])

        leaves[0].roots.add(roots[0])
        leaves[1].roots.add(roots[0])
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))

        leaves[0].roots.clear()
        leaves[1].roots.clear()
        self.assertEqual(roots[0].leaves, [])
        self.assertEqual(roots[1].leaves, [])

        leaves[0].roots = roots
        leaves[1].roots = roots
        self.assertEqual(set(roots[0].leaves), set(leaves[0:2]))
        self.assertEqual(set(roots[1].leaves), set(leaves[0:2]))

    def test_related_set_create(self):
        # many to one
        root = ManyToOneRoot()
        leaf = root.leaves.create(id='leaf')
        self.assertEqual(root.leaves, [leaf])
        self.assertEqual(leaf.root, root)

        # one to many
        leaf = OneToManyLeaf()
        root = leaf.roots.create(id='root')
        self.assertEqual(leaf.roots, [root])
        self.assertEqual(root.leaf, leaf)

        # many to many
        root_0 = ManyToManyRoot(id='root_0')

        leaf_0 = root_0.leaves.create(id='leaf_0')
        self.assertEqual(root_0.leaves, [leaf_0])
        self.assertEqual(leaf_0.roots, [root_0])

        root_1 = leaf_0.roots.create(id='root_1')
        self.assertEqual(root_1.leaves, [leaf_0])
        self.assertEqual(set(leaf_0.roots), set((root_0, root_1)))

    def test_related_set_filter_and_get_indedx(self):
        # many to one
        root = ManyToOneRoot()
        leaves = [
            ManyToOneLeaf(id='leaf_0'),
            ManyToOneLeaf(id='leaf_1'),
            ManyToOneLeaf(id='leaf_1'),
            ManyToOneLeaf(id='leaf_2'),
        ]
        root.leaves = leaves

        self.assertEqual(root.leaves.filter(id='leaf_0'), leaves[0:1])
        self.assertEqual(set(root.leaves.filter(id='leaf_1')), set(leaves[1:3]))
        self.assertEqual(root.leaves.filter(id='leaf_2'), leaves[3:4])

        self.assertEqual(root.leaves.get(id='leaf_0'), leaves[0])
        self.assertRaises(ValueError, lambda: root.leaves.get(id='leaf_1'))
        self.assertEqual(root.leaves.get(id='leaf_2'), leaves[3])

        leaves_list = [l for l in root.leaves]
        self.assertEqual(root.leaves.index(id='leaf_0'), leaves_list.index(leaves[0]))
        self.assertRaises(ValueError, lambda: root.leaves.index(id='leaf_1'))
        self.assertEqual(root.leaves.index(id='leaf_2'), leaves_list.index(leaves[3]))

        self.assertEqual(root.leaves.index(leaves[0]), leaves_list.index(leaves[0]))
        self.assertEqual(root.leaves.index(leaves[1]), leaves_list.index(leaves[1]))
        self.assertEqual(root.leaves.index(leaves[2]), leaves_list.index(leaves[2]))
        self.assertEqual(root.leaves.index(leaves[3]), leaves_list.index(leaves[3]))

        # one to many
        leaf = OneToManyLeaf()
        roots = [
            OneToManyRoot(id='root_0'),
            OneToManyRoot(id='root_1'),
            OneToManyRoot(id='root_1'),
            OneToManyRoot(id='root_2'),
        ]
        leaf.roots = roots

        self.assertEqual(leaf.roots.filter(id='root_0'), roots[0:1])
        self.assertEqual(set(leaf.roots.filter(id='root_1')), set(roots[1:3]))
        self.assertEqual(leaf.roots.filter(id='root_2'), roots[3:4])

        self.assertEqual(leaf.roots.get(id='root_0'), roots[0])
        self.assertRaises(ValueError, lambda: leaf.roots.get(id='root_1'))
        self.assertEqual(leaf.roots.get(id='root_2'), roots[3])

        # many to many
        roots = [
            ManyToManyRoot(id='root_0'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_1'),
            ManyToManyRoot(id='root_2'),
        ]
        leaf = ManyToManyLeaf(roots=roots)

        self.assertEqual(leaf.roots.filter(id='root_0'), roots[0:1])
        self.assertEqual(set(leaf.roots.filter(id='root_1')), set(roots[1:3]))
        self.assertEqual(leaf.roots.filter(id='root_2'), roots[3:4])

        self.assertEqual(leaf.roots.get(id='root_0'), roots[0])
        self.assertRaises(ValueError, lambda: leaf.roots.get(id='root_1'))
        self.assertEqual(leaf.roots.get(id='root_2'), roots[3])

    def test_validator(self):
        grandparent = Grandparent(id='root')
        parents = [
            Parent(grandparent=grandparent, id='node-0'),
            Parent(grandparent=grandparent),
        ]

        errors = core.Validator().run(parents)
        self.assertEqual(len(errors.invalid_objects), 2)
        self.assertEqual(errors.invalid_objects[0].object, parents[0])
        self.assertEqual(len(errors.invalid_objects[0].attributes), 1)
        self.assertEqual(errors.invalid_objects[0].attributes[0].attribute.name, 'id')

        roots = [
            Root(label='root-0'),
            Root(label='root-1'),
            Root(label='root-2'),
        ]
        errors = core.Validator().run(roots)
        self.assertEqual(errors, None)

        roots = [
            UniqueRoot(label='root_0', url='http://www.test.com'),
            UniqueRoot(label='root_0', url='http://www.test.com'),
            UniqueRoot(label='root_0', url='http://www.test.com'),
        ]
        errors = core.Validator().run(roots)

        self.assertEqual(len(errors.invalid_objects), 0)
        self.assertEqual(set([model.model for model in errors.invalid_models]), set((Root, UniqueRoot)))
        self.assertEqual(len(errors.invalid_models[0].attributes), 1)
        self.assertEqual(errors.invalid_models[0].attributes[0].attribute.name, 'label')
        self.assertEqual(len(errors.invalid_models[0].attributes[0].messages), 1)
        self.assertRegexpMatches(errors.invalid_models[0].attributes[0].messages[0], 'values must be unique')

    def test_inheritance(self):
        self.assertEqual(Leaf.Meta.attributes['name'].max_length, 255)
        self.assertEqual(UnrootedLeaf.Meta.attributes['name'].max_length, 10)

        self.assertEqual(set(Root.Meta.related_attributes.keys()), set(('leaves', 'leaves2')))

        self.assertEqual(Leaf.Meta.attributes['root'].primary_class, Leaf)
        self.assertEqual(Leaf.Meta.attributes['root'].related_class, Root)
        self.assertEqual(UnrootedLeaf.Meta.attributes['root'].primary_class, Leaf)
        self.assertEqual(UnrootedLeaf.Meta.attributes['root'].related_class, Root)
        self.assertEqual(Leaf3.Meta.attributes['root'].primary_class, Leaf)
        self.assertEqual(Leaf3.Meta.attributes['root'].related_class, Root)

        self.assertEqual(UnrootedLeaf.Meta.attributes['root2'].primary_class, UnrootedLeaf)
        self.assertEqual(UnrootedLeaf.Meta.attributes['root2'].related_class, Root)
        self.assertEqual(Leaf3.Meta.attributes['root2'].primary_class, UnrootedLeaf)
        self.assertEqual(Leaf3.Meta.attributes['root2'].related_class, Root)

        self.assertEqual(Root.Meta.related_attributes['leaves'].primary_class, Leaf)
        self.assertEqual(Root.Meta.related_attributes['leaves'].related_class, Root)

        self.assertEqual(Root.Meta.related_attributes['leaves2'].primary_class, UnrootedLeaf)
        self.assertEqual(Root.Meta.related_attributes['leaves2'].related_class, Root)

        root = Root()
        leaf = Leaf(root=root)
        unrooted_leaf = UnrootedLeaf(root=root)

        self.assertEqual(leaf.root, root)
        self.assertEqual(unrooted_leaf.root, root)
        self.assertEqual(set(root.leaves), set((leaf, unrooted_leaf, )))

    def test_attribute_inheritance(self):
        X = type('X', (core.Model, ), {'label': core.StringAttribute()})
        Y = type('Y', (X, ), {'label': core.StringAttribute()})

        x = X(label='x')
        y = Y(label='y')

        self.assertRaises(ValueError, lambda: type('Z', (X, ), {'label': 'z'}))

        Z = type('Z', (Y, ), {'label': core.StringAttribute()})
        z = Z(label='z')

    def test_unique(self):
        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='b', val1='b', val2='a'),
            UniqueTogetherRoot(val0='c', val1='c', val2='a'),
        ]
        self.assertEqual(UniqueTogetherRoot.validate_unique(roots), None)

        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='a', val1='b', val2='a'),
            UniqueTogetherRoot(val0='a', val1='c', val2='a'),
        ]
        errors = [x.attribute.name for x in UniqueTogetherRoot.validate_unique(roots).attributes]
        self.assertEqual(errors, ['val0'])

        roots = [
            UniqueTogetherRoot(val0='a', val1='a', val2='a'),
            UniqueTogetherRoot(val0='b', val1='a', val2='a'),
            UniqueTogetherRoot(val0='c', val1='c', val2='a'),
        ]
        errors = [x.attribute.name for x in UniqueTogetherRoot.validate_unique(roots).attributes]
        self.assertNotIn('val0', errors)
        self.assertEqual(len(errors), 1)

    def test_copy(self):
        g1 = Grandparent(id='root-1')
        p1 = [
            Parent(grandparent=g1, id='node-1-0'),
            Parent(grandparent=g1, id='node-1-1'),
        ]
        c1 = [
            Child(parent=p1[0], id='leaf-1-0-0'),
            Child(parent=p1[0], id='leaf-1-0-1'),
            Child(parent=p1[1], id='leaf-1-1-0'),
            Child(parent=p1[1], id='leaf-1-1-1'),
        ]

        copy = g1.copy()
        self.assertFalse(copy is g1)
        self.assertTrue(g1.is_equal(copy))

    def test_difference(self):
        g = [
            Grandparent(id='g', val='gparent_0'),
            Grandparent(id='g', val='gparent_0'),
        ]
        p = [
            Parent(grandparent=g[0], id='p_0', val='parent_0'),
            Parent(grandparent=g[0], id='p_1', val='parent_1'),
            Parent(grandparent=g[1], id='p_0', val='parent_0'),
            Parent(grandparent=g[1], id='p_1', val='parent_1'),
        ]
        c = [
            Child(parent=p[0], id='c_0_0', val='child_0_0'),
            Child(parent=p[0], id='c_0_1', val='child_0_1'),
            Child(parent=p[1], id='c_1_0', val='child_1_0'),
            Child(parent=p[1], id='c_1_1', val='child_1_1'),
            Child(parent=p[2], id='c_0_0', val='child_0_0'),
            Child(parent=p[2], id='c_0_1', val='child_0_1'),
            Child(parent=p[3], id='c_1_0', val='child_1_0'),
            Child(parent=p[3], id='c_1_1', val='child_1_1'),
        ]

        self.assertTrue(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), '')

        g[1].val = 'gparent_1'
        msg = (
            'Objects ("g", "g") have different attribute values:\n'
            '  `val` are not equal:\n'
            '    gparent_0 != gparent_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' + g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_1'
        c[4].val = 'child_3_0'
        msg = (
            'Objects ("g", "g") have different attribute values:\n'
            '  `val` are not equal:\n'
            '    gparent_0 != gparent_1\n'
            '  `children` are not equal:\n'
            '    element: "p_0" != element: "p_0"\n'
            '      Objects ("p_0", "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: "c_0_0" != element: "c_0_0"\n'
            '            Objects ("c_0_0", "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' + g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        msg = (
            'Objects ("g", "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: "p_0" != element: "p_0"\n'
            '      Objects ("p_0", "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: "c_0_0" != element: "c_0_0"\n'
            '            Objects ("c_0_0", "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' + g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        c[5].val = 'child_3_1'
        msg = (
            'Objects ("g", "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: "p_0" != element: "p_0"\n'
            '      Objects ("p_0", "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          element: "c_0_0" != element: "c_0_0"\n'
            '            Objects ("c_0_0", "c_0_0") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_0 != child_3_0\n'
            '          element: "c_0_1" != element: "c_0_1"\n'
            '            Objects ("c_0_1", "c_0_1") have different attribute values:\n'
            '              `val` are not equal:\n'
            '                child_0_1 != child_3_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' + g[0].difference(g[1]) + '\n\n' + msg)

        g[1].val = 'gparent_0'
        c[4].val = 'child_3_0'
        c[4].id = 'c_3_0'
        c[5].val = 'child_3_1'
        c[5].id = 'c_3_1'
        msg = (
            'Objects ("g", "g") have different attribute values:\n'
            '  `children` are not equal:\n'
            '    element: "p_0" != element: "p_0"\n'
            '      Objects ("p_0", "p_0") have different attribute values:\n'
            '        `children` are not equal:\n'
            '          No matching element c_0_0\n'
            '          No matching element c_0_1'
        )
        self.assertFalse(g[1].is_equal(g[0]))
        self.assertEqual(g[0].difference(g[1]), msg, '\n\n' + g[0].difference(g[1]) + '\n\n' + msg)

    def test_invalid_attribute_str(self):
        attr = core.Attribute()
        attr.name = 'attr'
        msgs = ['msg1', 'msg2\ncontinue']
        err = core.InvalidAttribute(attr, msgs)
        self.assertEqual(str(err),
                         "'{}':\n  {}\n  {}".format(attr.name, msgs[0], msgs[1].replace('\n', '\n  ')))

    def test_invalid_object_str(self):
        attrs = [
            core.Attribute(),
            core.Attribute(),
        ]
        attrs[0].name = 'attr0'
        attrs[1].name = 'attr1'
        msgs = ['msg00', 'msg01\ncontinue', 'msg10', 'msg11']
        attr_errs = [
            core.InvalidAttribute(attrs[0], msgs[0:2]),
            core.InvalidAttribute(attrs[1], msgs[2:4]),
        ]
        obj = Grandparent(id='gp')
        err = core.InvalidObject(obj, attr_errs)
        self.assertEqual(str(err), (
            "'{}':\n".format(attrs[0].name) +
            "  {}\n".format(msgs[0]) +
            "  {}\n".format(msgs[1].replace("\n", "\n  ")) +
            "'{}':\n".format(attrs[1].name) +
            "  {}\n".format(msgs[2]) +
            "  {}".format(msgs[3])
        ))

    def test_invalid_model_str(self):
        attrs = [
            core.Attribute(),
            core.Attribute(),
        ]
        attrs[0].name = 'attr0'
        attrs[1].name = 'attr1'
        msgs = ['msg00', 'msg01\ncontinue', 'msg10', 'msg11']
        attr_errs = [
            core.InvalidAttribute(attrs[0], msgs[0:2]),
            core.InvalidAttribute(attrs[1], msgs[2:4]),
        ]
        err = core.InvalidModel(Grandparent, attr_errs)
        self.assertEqual(str(err), (
            "'{}':\n".format(attrs[0].name) +
            "  {}\n".format(msgs[0]) +
            "  {}\n".format(msgs[1].replace("\n", "\n  ")) +
            "'{}':\n".format(attrs[1].name) +
            "  {}\n".format(msgs[2]) +
            "  {}".format(msgs[3])
        ))

    def test_invalid_object_set_exception(self):
        p = Parent(id='parent')
        invalid_model = core.InvalidModel(p, [])
        self.assertRaises(ValueError,
                          lambda: core.InvalidObjectSet([], [invalid_model, invalid_model]))

    # .. todo :: fix InvalidObjectSet.str()
    @unittest.skip('skipping until I (Arthur Goldberg) have time to do a detailed comparison')
    def test_invalid_object_set_str(self):
        attr = core.Attribute()
        attr.name = 'attr'
        msg = 'msg\ncontinue'
        attr_err = core.InvalidAttribute(attr, [msg, msg])
        gp = Grandparent(id='gp')
        p = Parent(id='parent')
        obj_err_gp = core.InvalidObject(gp, [attr_err, attr_err])
        obj_err_p = core.InvalidObject(p, [attr_err, attr_err])
        mod_err_gp = core.InvalidModel(Grandparent, [attr_err, attr_err])
        mod_err_p = core.InvalidModel(Parent, [attr_err, attr_err])
        err = core.InvalidObjectSet([obj_err_gp, obj_err_gp, obj_err_p, obj_err_p], [mod_err_gp, mod_err_p])

        self.assertEqual(str(err), (
            '{}:\n'.format(Grandparent.__name__) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '{}:\n'.format(Parent.__name__) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            "  '{}':\n".format(attr.name) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '    {}\n'.format(msg.replace('\n', '\n    ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '  \n' +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '    {}:\n'.format(attr.name) +
            '      {}\n'.format(msg.replace('\n', '\n      ')) +
            '      {}'.format(msg.replace('\n', '\n      '))
        ))

    def test_excel_col_name(self):
        self.assertRaises(ValueError, lambda: excel_col_name(0))
        self.assertRaises(ValueError, lambda: excel_col_name(''))
        self.assertEqual(excel_col_name(5), 'E')
        self.assertEqual(excel_col_name(2**14), 'XFD')

    @unittest.expectedFailure
    def test_maintain_unique(self):
        class test(core.Model):
            unique_attr = core.StringAttribute(unique=True)
        t1 = test(unique_attr='x')
        t2 = test(unique_attr='y')

        '''
        Currently (2/2017), validation of uniqueness is a static property that's
        ensured only when validate_unique() is called, that is, when a model's created or when
        validate_unique() is called by the user.

        Thus, this fails:
        '''
        with self.assertRaises(Exception) as context:
            t2.unique_attr = 'x'
        '''
        Todo fix:
            Index each unique & unique_together in their class object derived from Model. Obtain
            O(1) validation for each object instantiation or attribute change.
            Will also provide instance lookup by unique or unique_together attributes.

            Implementation:
                create instance:
                    redefine __new__() to insert a weak reference to the object in a dict in the class

                modify field:
                    modify __setattr__() to test uniqueness, and raise exception if test fails

                delete object:
                    use a finalizer to remove object from the class dict
        '''

    def test_sort(self):
        roots = [
            Root(label='c'),
            Root(label='d'),
            Root(label='a'),
            Root(label='b'),
        ]

        roots2 = Root.sort(roots)
        self.assertEqual(roots[0].label, 'c')
        self.assertEqual(roots[1].label, 'd')
        self.assertEqual(roots[2].label, 'a')
        self.assertEqual(roots[3].label, 'b')

        self.assertEqual(roots2[0].label, 'a')
        self.assertEqual(roots2[1].label, 'b')
        self.assertEqual(roots2[2].label, 'c')
        self.assertEqual(roots2[3].label, 'd')

        self.assertEqual(roots2[0], roots[2])
        self.assertEqual(roots2[1], roots[3])
        self.assertEqual(roots2[2], roots[0])
        self.assertEqual(roots2[3], roots[1])

    def test_normalize(self):
        class NormNodeLevel0(core.Model):
            label = core.StringAttribute(primary=True, unique=True)

        class NormNodeLevel1(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parent = core.ManyToOneAttribute(NormNodeLevel0, related_name='children')

        class NormNodeLevel2(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parent = core.ManyToOneAttribute(NormNodeLevel1, related_name='children')

        class NormNodeLevel3(core.Model):
            label = core.StringAttribute()

        # example
        node_0 = NormNodeLevel0()

        node_0_c = node_0.children.create(label='c')
        node_0_a = node_0.children.create(label='a')
        node_0_b = node_0.children.create(label='b')

        node_0_a_a = node_0_a.children.create(label='a_a')
        node_0_a_c = node_0_a.children.create(label='a_c')
        node_0_a_b = node_0_a.children.create(label='a_b')

        node_0_b_a = node_0_b.children.create(label='b_a')
        node_0_b_c = node_0_b.children.create(label='b_c')
        node_0_b_b = node_0_b.children.create(label='b_b')

        node_0_c_a = node_0_c.children.create(label='c_a')
        node_0_c_c = node_0_c.children.create(label='c_c')
        node_0_c_b = node_0_c.children.create(label='c_b')

        # test
        node_0.normalize()

        self.assertEqual(node_0.children, [node_0_a, node_0_b, node_0_c])

        self.assertEqual(node_0.children[0].children, [node_0_a_a, node_0_a_b, node_0_a_c])
        self.assertEqual(node_0.children[1].children, [node_0_b_a, node_0_b_b, node_0_b_c])
        self.assertEqual(node_0.children[2].children, [node_0_c_a, node_0_c_b, node_0_c_c])
