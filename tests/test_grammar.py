""" Tests for using grammars

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-23
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables import io
import obj_tables.grammar
import os.path
import shutil
import tempfile
import unittest
import wc_utils.workbook.io


class GrammarTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_one_to_many(self):
        class Parent(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            age = core.IntegerAttribute()

            class Meta(core.Model.Meta):
                table_format = core.TableFormat.cell

        grammar_filename = os.path.join(self.dirname, 'grammar.lark')
        with open(grammar_filename, 'w') as file:
            file.write('''
                    ?start: parent ("; " parent)*
                    parent: PARENT__ID ": " PARENT__NAME " (" PARENT__AGE ")"
                    PARENT__ID: /[a-zA-Z0-9_]+/
                    PARENT__NAME: /[a-zA-Z0-9_\-][a-zA-Z0-9_\- ]*[a-zA-Z0-9_\-]/
                    PARENT__AGE: /[0-9]+/
                    ''')

        class OneToManyParentGrammarAttribute(obj_tables.grammar.ToManyGrammarAttribute, core.OneToManyAttribute):
            grammar_path = grammar_filename

            def serialize(self, values, encoded=None):
                serialized_value = []
                for parent in values:
                    serialized_value.append('{}: {} ({})'.format(
                        parent.id, parent.name, parent.age))

                return '; '.join(serialized_value)

            class Transformer(obj_tables.grammar.ToManyGrammarTransformer):
                @obj_tables.grammar.v_args(inline=True)
                def parent(self, *args):
                    kwargs = {}
                    for arg in args:
                        cls_name, _, attr_name = arg.type.partition('__')
                        kwargs[attr_name.lower()] = arg.value

                    return self.get_or_create_model_obj(Parent, **kwargs)

        class Child(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            parents = OneToManyParentGrammarAttribute(Parent, related_name='child')

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'name', 'parents')

        c_1 = Child(id='c_1', name='c 1')
        c_2 = Child(id='c_2', name='c 2')
        p_11 = Parent(id='p_11', name='p 11', age=11)
        p_12 = Parent(id='p_12', name='p 12', age=12)
        p_21 = Parent(id='p_21', name='p 21', age=21)
        p_22 = Parent(id='p_22', name='p 22', age=22)
        c_1.parents = [p_11, p_12]
        c_2.parents = [p_21, p_22]
        objects = {
            Parent: [p_11, p_12, p_21, p_22],
            Child: [c_1, c_2],
        }

        filename = os.path.join(self.dirname, 'test.xlsx')
        io.WorkbookWriter().run(filename, objects[Child], models=[Child, Parent])

        objects_b = io.WorkbookReader().run(filename, models=[Child, Parent], group_objects_by_model=True)

        parents = sorted(objects[Parent], key=lambda parent: parent.id)
        parents_b = sorted(objects_b[Parent], key=lambda parent: parent.id)
        for parent, parent_b in zip(parents, parents_b):
            self.assertTrue(parent_b.is_equal(parent))

        children = sorted(objects[Child], key=lambda child: child.id)
        children_b = sorted(objects_b[Child], key=lambda child: child.id)
        for child, child_b in zip(children, children_b):
            self.assertTrue(child_b.is_equal(child))

        # test deserialization
        self.assertEqual(Child.parents.deserialize(None, {}), ([], None))
        self.assertEqual(Child.parents.deserialize('', {}), ([], None))

        # test Transformer.get_or_create_model_obj
        class NoPrimary(core.Model):
            name = core.StringAttribute()

            def serialize(self):
                return self.name

        Child.parents.Transformer({}).get_or_create_model_obj(NoPrimary,
                                                              name='new')

        with self.assertRaisesRegex(ValueError, 'Insufficient information to make new instance'):
            Child.parents.Transformer({}).get_or_create_model_obj(NoPrimary)

        with self.assertRaisesRegex(ValueError, 'Insufficient information to make new instance'):
            Child.parents.Transformer({}).get_or_create_model_obj(Child,
                                                                  _serialized_val='c_new')

    def test_many_to_many(self):
        class Parent(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            age = core.IntegerAttribute()

            class Meta(core.Model.Meta):
                table_format = core.TableFormat.cell

        class ManyToManyParentGrammarAttribute(obj_tables.grammar.ToManyGrammarAttribute, core.ManyToManyAttribute):
            grammar = '''
                    ?start: parent ("; " parent)*
                    parent: PARENT__ID ": " PARENT__NAME " (" PARENT__AGE ")"
                    PARENT__ID: /[a-zA-Z0-9_]+/
                    PARENT__NAME: /[a-zA-Z0-9_\-][a-zA-Z0-9_\- ]*[a-zA-Z0-9_\-]/
                    PARENT__AGE: /[a-z0-9]+/
                    '''

            def serialize(self, values, encoded=None):
                serialized_value = []
                for parent in values:
                    serialized_value.append('{}: {} ({})'.format(
                        parent.id, parent.name, parent.age))

                return '; '.join(serialized_value)

        class Child(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            parents = ManyToManyParentGrammarAttribute(Parent, related_name='children')

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'name', 'parents')

        c_1 = Child(id='c_1', name='c 1')
        c_2 = Child(id='c_2', name='c 2')
        p_1 = Parent(id='p_1', name='p 1', age=1)
        p_2 = Parent(id='p_2', name='p 2', age=2)
        p_12 = Parent(id='p_12', name='p 12', age=12)
        c_1.parents = [p_1, p_12]
        c_2.parents = [p_2, p_12]
        objects = {
            Parent: [p_1, p_2, p_12],
            Child: [c_1, c_2],
        }

        filename = os.path.join(self.dirname, 'test.xlsx')
        io.WorkbookWriter().run(filename, objects[Child], models=[Child, Parent])

        objects_b = io.WorkbookReader().run(filename, models=[Child, Parent], group_objects_by_model=True)

        parents = sorted(objects[Parent], key=lambda parent: parent.id)
        parents_b = sorted(objects_b[Parent], key=lambda parent: parent.id)
        for parent, parent_b in zip(parents, parents_b):
            self.assertTrue(parent_b.is_equal(parent))

        children = sorted(objects[Child], key=lambda child: child.id)
        children_b = sorted(objects_b[Child], key=lambda child: child.id)
        for child, child_b in zip(children, children_b):
            self.assertTrue(child_b.is_equal(child))

        # test parsing error
        wb = wc_utils.workbook.io.read(filename)
        wb['!Children'][2][2] = 'old_parent: old name (old)'
        filename2 = os.path.join(self.dirname, 'test2.xlsx')
        wc_utils.workbook.io.write(filename2, wb)
        with self.assertRaisesRegex(ValueError, 'Unable to clean'):
            objects_b = io.WorkbookReader().run(filename2, models=[Child, Parent], group_objects_by_model=True)

    def test_no_grammar(self):
        class OneToManyParentGrammarAttribute(obj_tables.grammar.ToManyGrammarAttribute, core.OneToManyAttribute):
            def serialize(self, values, encoded=None):
                pass

            class Transformer(obj_tables.grammar.ToManyGrammarTransformer):
                pass

        with self.assertRaisesRegex(ValueError, 'grammar must be defined'):
            parents = OneToManyParentGrammarAttribute('Parent', related_name='child')
