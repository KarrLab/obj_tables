""" Tests for using grammars

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-23
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import core
from obj_tables import io
from obj_tables import grammar
import os.path
import shutil
import tempfile
import unittest


class GrammarTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_one_to_many(self):
        class Parent(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()

            class Meta(core.Model.Meta):
                table_format = core.TableFormat.cell

        class OneToManyParentGrammarAttribute(grammar.ToManyGrammarAttribute, core.OneToManyAttribute):
            GRAMMAR = '''
                    ?start: parent ("; " parent)*
                    parent: PARENT_ID ": " PARENT_NAME
                    PARENT_ID: /[a-zA-Z0-9_]+/
                    PARENT_NAME: /[a-zA-Z0-9_\- ]+/
                    '''

            def serialize(self, values, encoded=None):
                """ Serialize related object

                Args:
                    values (:obj:`list` of :obj:`Model`): Python representation
                    encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

                Returns:
                    :obj:`str`: simple Python representation
                """
                serialized_value = []
                for parent in values:
                    serialized_value.append('{}: {}'.format(parent.id, parent.name))

                return '; '.join(serialized_value)

            class Transformer(grammar.Transformer):
                """ Transforms parse trees into a list of instances of :obj:`core.Model` """
                @grammar.v_args(inline=True)
                def parent(self, *args):
                    kwargs = {}
                    for arg in args:
                        if arg.type == 'PARENT_ID':
                            kwargs['id'] = arg.value
                        elif arg.type == 'PARENT_NAME':
                            kwargs['name'] = arg.value

                    return self.get_or_create(Parent, kwargs['id'], **kwargs)

        class Child(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            parents = OneToManyParentGrammarAttribute(Parent, related_name='child')

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'name', 'parents')

        c_1 = Child(id='c_1', name='c 1')
        c_2 = Child(id='c_2', name='c 2')
        p_11 = Parent(id='p_11', name='p 11')
        p_12 = Parent(id='p_12', name='p 12')
        p_21 = Parent(id='p_21', name='p 21')
        p_22 = Parent(id='p_22', name='p 22')
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

    def test_many_to_many(self):
        class Parent(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()

            class Meta(core.Model.Meta):
                table_format = core.TableFormat.cell

        class ManyToManyParentGrammarAttribute(grammar.ToManyGrammarAttribute, core.ManyToManyAttribute):
            GRAMMAR = '''
                    ?start: parent ("; " parent)*
                    parent: PARENT_ID ": " PARENT_NAME
                    PARENT_ID: /[a-zA-Z0-9_]+/
                    PARENT_NAME: /[a-zA-Z0-9_\- ]+/
                    '''

            def serialize(self, values, encoded=None):
                """ Serialize related object

                Args:
                    values (:obj:`list` of :obj:`Model`): Python representation
                    encoded (:obj:`dict`, optional): dictionary of objects that have already been encoded

                Returns:
                    :obj:`str`: simple Python representation
                """
                serialized_value = []
                for parent in values:
                    serialized_value.append('{}: {}'.format(parent.id, parent.name))

                return '; '.join(serialized_value)

            class Transformer(grammar.Transformer):
                """ Transforms parse trees into a list of instances of :obj:`core.Model` """
                @grammar.v_args(inline=True)
                def parent(self, *args):
                    kwargs = {}
                    for arg in args:
                        if arg.type == 'PARENT_ID':
                            kwargs['id'] = arg.value
                        elif arg.type == 'PARENT_NAME':
                            kwargs['name'] = arg.value

                    return self.get_or_create(Parent, kwargs['id'], **kwargs)

        class Child(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            parents = ManyToManyParentGrammarAttribute(Parent, related_name='children')

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'name', 'parents')

        c_1 = Child(id='c_1', name='c 1')
        c_2 = Child(id='c_2', name='c 2')
        p_1 = Parent(id='p_1', name='p 1')
        p_2 = Parent(id='p_2', name='p 2')
        p_12 = Parent(id='p_12', name='p 12')
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
