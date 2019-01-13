""" Test merging

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-01-13
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_model import core
import unittest


class MergeTestCase(unittest.TestCase):
    def test_gen_serialized_val_obj_map(self):
        class Gen1(core.Model):
            id = core.SlugAttribute()

        class Gen2(core.Model):
            id = core.SlugAttribute()
            parent = core.ManyToOneAttribute(Gen1, related_name='children')

        class Gen3(core.Model):
            id = core.SlugAttribute()
            parent = core.ManyToOneAttribute(Gen2, related_name='children')

        gen_1 = Gen1(id='gen_1')
        gen_2_1 = gen_1.children.create(id='gen_2_1')
        gen_2_2 = gen_1.children.create(id='gen_2_2')
        gen_3_1_1 = gen_2_1.children.create(id='gen_3_1_1')
        gen_3_1_2 = gen_2_1.children.create(id='gen_3_1_2')
        gen_3_2_1 = gen_2_2.children.create(id='gen_3_2_1')
        gen_3_2_2 = gen_2_2.children.create(id='gen_3_2_2')

        self.assertEqual(gen_1.gen_serialized_val_obj_map(), {
            Gen1: {'gen_1': gen_1},
            Gen2: {'gen_2_1': gen_2_1, 'gen_2_2': gen_2_2},
            Gen3: {
                'gen_3_1_1': gen_3_1_1,
                'gen_3_1_2': gen_3_1_2,
                'gen_3_2_1': gen_3_2_1,
                'gen_3_2_2': gen_3_2_2,
            },
        })

        # test error
        gen_3_2_2 = gen_2_2.children.create(id='gen_3_2_2')
        with self.assertRaisesRegex(ValueError, 'is not unique'):
            gen_1.gen_serialized_val_obj_map()

    def test_gen_merge_map(self):
        class Gen1(core.Model):
            id = core.SlugAttribute()

        class Gen2(core.Model):
            id = core.SlugAttribute()
            parents = core.ManyToManyAttribute(Gen1, related_name='children')

        class Gen3(core.Model):
            id = core.SlugAttribute()
            parents = core.ManyToManyAttribute(Gen2, related_name='children')

        gen_a_1 = Gen1(id='gen_a_1')
        gen_a_2_1 = gen_a_1.children.create(id='gen_2_1')
        gen_a_2_2 = gen_a_1.children.create(id='gen_2_2_a')
        gen_a_3_1_1 = gen_a_2_1.children.create(id='gen_3_1_1')
        gen_a_3_1_2 = gen_a_2_1.children.create(id='gen_3_1_2')
        gen_a_3_2_1 = gen_a_2_2.children.create(id='gen_3_2_1')
        gen_a_3_2_2 = gen_a_2_2.children.create(id='gen_3_2_2_a')

        gen_b_1 = Gen1(id='gen_b_1')
        gen_b_2_1 = gen_b_1.children.create(id='gen_2_1')
        gen_b_2_2 = gen_b_1.children.create(id='gen_2_2_b')
        gen_b_3_1_1 = gen_b_2_1.children.create(id='gen_3_1_1')
        gen_b_3_1_2 = gen_b_2_1.children.create(id='gen_3_1_2')
        gen_b_3_2_1 = gen_b_2_2.children.create(id='gen_3_2_1')
        gen_b_3_2_2 = gen_b_2_2.children.create(id='gen_3_2_2_b')

        b_in_a, b_not_in_a = gen_a_1.gen_merge_map(gen_b_1)
        a_in_b, a_not_in_b = gen_b_1.gen_merge_map(gen_a_1)
        self.assertEqual(b_in_a, {
            gen_b_1: gen_a_1,
            gen_b_2_1: gen_a_2_1,
            gen_b_3_1_1: gen_a_3_1_1,
            gen_b_3_1_2: gen_a_3_1_2,
            gen_b_3_2_1: gen_a_3_2_1,
        })
        self.assertEqual(a_in_b, {
            gen_a_1: gen_b_1,
            gen_a_2_1: gen_b_2_1,
            gen_a_3_1_1: gen_b_3_1_1,
            gen_a_3_1_2: gen_b_3_1_2,
            gen_a_3_2_1: gen_b_3_2_1,
        })
        self.assertEqual(set(b_not_in_a), set([gen_b_2_2, gen_b_3_2_2]))
        self.assertEqual(set(a_not_in_b), set([gen_a_2_2, gen_a_3_2_2]))

        # test error
        gen_b_2_1.parents.create(id='gen_a_1')
        with self.assertRaisesRegex(ValueError, 'Other must map to self'):
            gen_b_1.gen_merge_map(gen_a_1)

    def test_merge_literal_attribute(self):
        class Model(core.Model):
            id = core.StringAttribute()
        attr = Model.id

        left = Model(id='a')
        right = Model(id='a')
        attr.merge(left, right, {}, {})

        right.id = 'b'
        with self.assertRaisesRegex(ValueError, 'must be equal'):
            attr.merge(left, right, {}, {})

    def test_merge_float_attribute(self):
        class Model(core.Model):
            value = core.FloatAttribute()
        attr = Model.value

        left = Model(value=1.)
        right = Model(value=1.)
        attr.merge(left, right, {}, {})

        right.value = 2.
        with self.assertRaisesRegex(ValueError, 'must be equal'):
            attr.merge(left, right, {}, {})

        left = Model(value=float('nan'))
        right = Model(value=float('nan'))
        attr.merge(left, right, {}, {})

        right.value = 2.
        with self.assertRaisesRegex(ValueError, 'must be equal'):
            attr.merge(left, right, {}, {})

    def test_merge_one_to_one_attribute(self):
        class Parent(core.Model):
            id = core.SlugAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            parent = core.OneToOneAttribute(Parent, related_name='child')
        attr = Child.parent

        # Ex 1
        c_1 = Child(id='c')

        c_2 = Child(id='c')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, None)

        # Ex 2
        c_1 = Child(id='c')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, p_2)

        # Ex 3
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 4
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 5
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')
        
        with self.assertRaisesRegex(ValueError, 'Cannot join'):
            attr.merge(c_1, c_2, {}, {})

        # Ex 6
        c_1 = Child(id='c')
        p_1 = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 7
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

    def test_merge_many_to_one_attribute(self):
        class Parent(core.Model):
            id = core.SlugAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            parent = core.ManyToOneAttribute(Parent, related_name='children')
        attr = Child.parent

        # Ex 1
        c_1 = Child(id='c')

        c_2 = Child(id='c')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, None)

        # Ex 2
        c_1 = Child(id='c')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, p_2)

        # Ex 3
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')

        attr.merge(c_1, c_2, {c_2: c_1}, {c_1: c_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 4
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 5
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')
        
        with self.assertRaisesRegex(ValueError, 'Cannot join'):
            attr.merge(c_1, c_2, {}, {})

        # Ex 6
        c_1 = Child(id='c')
        p_1 = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = c_2.parent = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

        # Ex 7
        c_1 = Child(id='c')
        p_1 = c_1.parent = Parent(id='p')

        c_2 = Child(id='c')
        p_2 = Parent(id='p')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parent, p_1)

    def test_merge_one_to_many_attribute(self):
        class Parent(core.Model):
            id = core.SlugAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            parents = core.OneToManyAttribute(Parent, related_name='child')
        attr = Child.parents

        # Ex 1
        c_1 = Child(id='c_1')

        c_2 = Child(id='c_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [])

        # Ex 2
        c_1 = Child(id='c_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_2])

        # Ex 3
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 4
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_1, p_2])

        # Ex 5 
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_1')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 5
        p_1 = Parent(id='p_1')

        p_2 = Parent(id='p_2')
        c_2 = p_2.child = Child(id='c_2')

        attr.merge(c_2, c_2, {}, {})
        self.assertEqual(p_1.child, None)

        # Ex 6
        p_1 = Parent(id='p_1')
        c_1 = Child(id='c_2')

        p_2 = Parent(id='p_2')
        c_2 = p_2.child = Child(id='c_2')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(p_1.child, c_1)

        # Ex 7
        p_1 = Parent(id='p_1')
        c_1 = p_1.child = Child(id='c_2')

        p_2 = Parent(id='p_2')
        c_2 = Child(id='c_2')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(p_1.child, c_1)

        # Ex 8
        p_1 = Parent(id='p_1')
        c_1 = p_1.child = Child(id='c_1')

        p_2 = Parent(id='p_2')

        attr.merge(c_1, c_1, {}, {})
        self.assertEqual(p_1.child, c_1)

        # Ex 9
        c_1 = Child(id='c_1')
        p_1_1 = c_1.parents.create(id='p_1')
        p_1_2 = c_1.parents.create(id='p_2')

        c_2 = Child(id='c_2')
        p_2_1 = c_2.parents.create(id='p_1')
        p_2_3 = c_2.parents.create(id='p_3')

        attr.merge(c_1, c_2, {p_2_1: p_1_1}, {p_1_1: p_2_1})
        self.assertEqual(c_1.parents, [p_1_1, p_1_2, p_2_3])

        # Ex 10
        c_1 = Child(id='c_1')
        p_1_1 = c_1.parents.create(id='p_1')
        p_1_2 = c_1.parents.create(id='p_2')

        c_2 = Child(id='c_2')
        p_2_1 = c_2.parents.create(id='p_1')
        p_2_2 = Parent(id='p_2')

        attr.merge(c_1, c_2, {p_2_1: p_1_1, p_2_2: p_1_2}, {p_1_1: p_2_1, p_1_2: p_2_2})
        self.assertEqual(c_1.parents, [p_1_1, p_1_2])

        # Ex 11
        c_1 = Child(id='c_1')
        p_1_1 = c_1.parents.create(id='p_1')
        p_1_2 = Parent(id='p_2')

        c_2 = Child(id='c_2')
        p_2_1 = c_2.parents.create(id='p_1')
        p_2_2 = c_2.parents.create(id='p_2')

        attr.merge(c_1, c_2, {p_2_1: p_1_1, p_2_2: p_1_2}, {p_1_1: p_2_1, p_1_2: p_2_2})
        self.assertEqual(c_1.parents, [p_1_1, p_1_2])

    def test_merge_many_to_many_attribute(self):
        class Parent(core.Model):
            id = core.SlugAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            parents = core.ManyToManyAttribute(Parent, related_name='children')
        attr = Child.parents

        # Ex 1
        c_1 = Child(id='c_1')

        c_2 = Child(id='c_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [])

        # Ex 2
        c_1 = Child(id='c_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_2])

        # Ex 3
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 4
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_2')

        attr.merge(c_1, c_2, {}, {})
        self.assertEqual(c_1.parents, [p_1, p_2])

        # Ex 5 
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_1')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 6
        c_1 = Child(id='c_1')
        p_1 = Parent(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = c_2.parents.create(id='p_1')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 7 
        c_1 = Child(id='c_1')
        p_1 = c_1.parents.create(id='p_1')

        c_2 = Child(id='c_2')
        p_2 = Parent(id='p_1')

        attr.merge(c_1, c_2, {p_2: p_1}, {p_1: p_2})
        self.assertEqual(c_1.parents, [p_1])

        # Ex 8
        p_1 = Parent(id='p_1')

        p_2 = Parent(id='p_2')
        c_2 = p_2.children.create(id='c_2')

        attr.merge(c_2, c_2, {}, {})
        self.assertEqual(p_1.children, [])

        # Ex 9
        p_1 = Parent(id='p_1')
        c_1 = p_1.children.create(id='c_1')

        p_2 = Parent(id='p_2')

        attr.merge(c_1, c_1, {}, {})
        self.assertEqual(p_1.children, [c_1])

    def test_merge_attributes(self):
        class Model(core.Model):
            attr_1 = core.StringAttribute()
            attr_2 = core.StringAttribute()

            class Meta(core.Model.Meta):
                merge = core.ModelMerge.join

        model_1 = Model(attr_1='a_1', attr_2='a_2')
        model_2 = Model(attr_1='a_1', attr_2='a_2')

        model_1.merge_attrs(model_1, {}, {})
        model_1.merge_attrs(model_2, {}, {})

        model_2.attr_1 = 'b_1'
        with self.assertRaisesRegex(ValueError, 'must be equal'):
            model_1.merge_attrs(model_2, {}, {})
        with self.assertRaisesRegex(ValueError, 'must be equal'):
            model_2.merge_attrs(model_1, {}, {})

        Model.Meta.merge = core.ModelMerge.append
        model_1.merge_attrs(model_1, {}, {})
        with self.assertRaisesRegex(ValueError, 'cannot be joined'):
            model_1.merge_attrs(model_2, {}, {})

    def test_merge(self):
        class Parent(core.Model):
            id = core.SlugAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            parents = core.ManyToManyAttribute(Parent, related_name='children')

        p_a_1 = Parent(id='p_1')
        p_a_2 = Parent(id='p_2')
        c_a_1_1 = p_a_1.children.create(id='c_1')
        c_a_1_2 = p_a_1.children.create(id='c_2')
        p_a_2.children.append(c_a_1_1)

        p_b_1 = Parent(id='p_1')
        p_b_3 = Parent(id='p_3')
        c_b_1_1 = p_b_1.children.create(id='c_1')
        c_b_1_3 = p_b_1.children.create(id='c_3')
        p_b_3.children.append(c_b_1_1)

        p_c_1 = Parent(id='p_1')
        p_c_2 = Parent(id='p_2')
        p_c_3 = Parent(id='p_3')
        c_c_1_1 = p_c_1.children.create(id='c_1')
        c_c_1_2 = p_c_1.children.create(id='c_2')
        c_c_1_3 = p_c_1.children.create(id='c_3')
        p_c_2.children.append(c_c_1_1)
        p_c_3.children.append(c_c_1_1)

        p_a_1.merge(p_b_1)
        self.assertTrue(p_a_1.is_equal(p_c_1))

