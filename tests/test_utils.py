""" Data model to represent models.

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""
from six import string_types
import tempfile
import sys
import unittest
import shutil
from obj_model import core, utils


class Root(core.Model):
    id = core.StringAttribute(max_length=1, primary=True, unique=True, verbose_name='Identifier')


class Node(core.Model):
    id = core.StringAttribute(max_length=2, primary=True, unique=True)
    root = core.ManyToOneAttribute(Root, related_name='nodes')


class Leaf(core.Model):
    id = core.StringAttribute(primary=True)
    node = core.ManyToOneAttribute(Node, related_name='leaves')


class TestUtils(unittest.TestCase):

    def setUp(self):
        self.root = Root(id='root')
        self.nodes = [
            Node(root=self.root, id='node-0'),
            Node(root=self.root, id='node-1'),
        ]
        self.leaves = [
            Leaf(node=self.nodes[0], id='leaf-0-0'),
            Leaf(node=self.nodes[0], id='leaf-0-1'),
            Leaf(node=self.nodes[1], id='leaf-1-0'),
            Leaf(node=self.nodes[1], id='leaf-1-1'),
        ]

    def test_get_related_models(self):
        class DisjointParent(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class DisjointChild(core.Model):
            parent = core.ManyToOneAttribute(DisjointParent, related_name='children')

        self.assertEqual(set(utils.get_related_models(Root)), set([Node, Leaf]))
        self.assertEqual(set(utils.get_related_models(Node)), set([Root, Leaf]))
        self.assertEqual(set(utils.get_related_models(Leaf)), set([Root, Node]))
        self.assertEqual(set(utils.get_related_models(Root, include_root_model=True)), set([Root, Node, Leaf]))
        self.assertEqual(set(utils.get_related_models(Node, include_root_model=True)), set([Root, Node, Leaf]))
        self.assertEqual(set(utils.get_related_models(Leaf, include_root_model=True)), set([Root, Node, Leaf]))

        self.assertEqual(set(utils.get_related_models(DisjointParent)), set([DisjointChild]))
        self.assertEqual(set(utils.get_related_models(DisjointChild)), set([DisjointParent]))
        self.assertEqual(set(utils.get_related_models(DisjointParent, include_root_model=True)), set([DisjointParent, DisjointChild]))
        self.assertEqual(set(utils.get_related_models(DisjointChild, include_root_model=True)), set([DisjointChild, DisjointParent]))

    def test_get_attribute_by_name(self):
        self.assertEqual(utils.get_attribute_by_name(Root, 'id'), Root.Meta.attributes['id'])
        self.assertEqual(utils.get_attribute_by_name(Root, 'id2'), None)

        self.assertEqual(utils.get_attribute_by_name(Root, 'ID', case_insensitive=True), Root.Meta.attributes['id'])
        self.assertEqual(utils.get_attribute_by_name(Root, 'ID', case_insensitive=False), None)

    def test_get_attribute_by_verbose_name(self):
        self.assertEqual(utils.get_attribute_by_verbose_name(Root, 'Identifier'), Root.Meta.attributes['id'])
        self.assertEqual(utils.get_attribute_by_verbose_name(Root, 'Identifier2'), None)

        self.assertEqual(utils.get_attribute_by_verbose_name(
            Root, 'identifier', case_insensitive=True), Root.Meta.attributes['id'])
        self.assertEqual(utils.get_attribute_by_verbose_name(Root, 'identifier', case_insensitive=False), None)

    def test_group_objects_by_model(self):
        (root, nodes, leaves) = (self.root, self.nodes, self.leaves)
        objects = [root] + nodes + leaves
        grouped_objects = utils.group_objects_by_model(objects)
        self.assertEqual(grouped_objects[Root], [root])
        self.assertEqual(set(grouped_objects[Node]), set(nodes))
        self.assertEqual(set(grouped_objects[Leaf]), set(leaves))

    def test_get_related_errors(self):
        (root, nodes, leaves) = (self.root, self.nodes, self.leaves)

        errors = utils.get_related_errors(root)
        self.assertEqual(set((x.object for x in errors.invalid_objects)), set((root, )) | set(nodes))

        errors_by_model = errors.get_object_errors_by_model()
        self.assertEqual(set((x.__name__ for x in errors_by_model.keys())), set(('Root', 'Node')))

        self.assertEqual(len(errors_by_model[Root]), 1)
        self.assertEqual(len(errors_by_model[Node]), 2)

        self.assertIsInstance(str(errors), string_types)

    def test_get_related_errors_no_related(self):
        class LoneNode(core.Model):
            id = core.StringAttribute(max_length=1, primary=True, unique=True, verbose_name='Identifier')

        node = LoneNode(id='l')
        errors = utils.get_related_errors(node)
        self.assertEqual(errors, None)

        node = LoneNode(id='lone_node')
        errors = utils.get_related_errors(node)
        self.assertEqual([invalid_obj.object for invalid_obj in errors.invalid_objects], [node])

    def test_get_component_by_id(self):
        class Test(core.Model):
            val = core.StringAttribute()

        (root, nodes, leaves) = (self.root, self.nodes, self.leaves)
        self.assertEqual(utils.get_component_by_id(nodes, 'node-0'), nodes[0])
        self.assertEqual(utils.get_component_by_id(nodes, 'node-1'), nodes[1])
        self.assertEqual(utils.get_component_by_id(nodes, 'x'), None)

        test = Test(val='x')
        self.assertRaises(AttributeError,
                          lambda: utils.get_component_by_id([test], 'x'))
        self.assertEqual(utils.get_component_by_id([test], 'x', identifier='val'), test)

    def test_randomize(self):
        class NormNodeLevel0(core.Model):
            label = core.StringAttribute(primary=True, unique=True)

        class NormNodeLevel1(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parents = core.ManyToManyAttribute(NormNodeLevel0, related_name='children')

        class NormNodeLevel2(core.Model):
            label = core.StringAttribute(primary=True, unique=True)
            parents = core.ManyToManyAttribute(NormNodeLevel1, related_name='children')

        nodes0 = []
        nodes1 = []
        nodes2 = []
        n = 20
        for i in range(n):
            nodes0.append(NormNodeLevel0(label='node_0_{}'.format(i)))

        for i in range(n):
            nodes1.append(NormNodeLevel1(label='node_1_{}'.format(i), parents=[
                          nodes0[(i) % n], nodes0[(i + 1) % n], nodes0[(i + 2) % n], ]))

        for i in range(n):
            nodes2.append(NormNodeLevel2(label='node_2_{}'.format(i), parents=[
                          nodes1[(i) % n], nodes1[(i + 1) % n], nodes1[(i + 2) % n], ]))

        def check_sorted():
            for i in range(n):
                i_childs = sorted([(i - 2) % n, (i - 1) % n, (i - 0) % n, ])
                for i_child, child in zip(i_childs, nodes0[i].children):
                    if child.label != 'node_1_{}'.format(i_child):
                        return False

                i_parents = sorted([(i + 0) % n, (i + 1) % n, (i + 2) % n, ])
                for i_parent, parent in zip(i_parents, nodes1[i].parents):
                    if parent.label != 'node_0_{}'.format(i_parent):
                        return False

                i_childs = sorted([(i - 2) % n, (i - 1) % n, (i - 0) % n, ])
                for i_child, child in zip(i_childs, nodes1[i].children):
                    if child.label != 'node_2_{}'.format(i_child):
                        return False

                i_parents = sorted([(i + 0) % n, (i + 1) % n, (i + 2) % n, ])
                for i_parent, parent in zip(i_parents, nodes2[i].parents):
                    if parent.label != 'node_1_{}'.format(i_parent):
                        return False

                return True

        # sort and check sorted
        nodes0[0].normalize()
        self.assertTrue(check_sorted())

        # randomize
        n_random = 0
        n_trials = 100
        for i in range(n_trials):
            utils.randomize_object_graph(nodes0[0])
            n_random += (check_sorted() == False)

            nodes0[0].normalize()
            self.assertTrue(check_sorted())

        self.assertGreater(n_random, 0.9 * n_trials)


    class MedadataModel(core.Model):
        url = core.StringAttribute()
        branch = core.StringAttribute()
        revision = core.StringAttribute()

    def test_set_git_repo_metadata_from_path(self):

        medadata_model = self.MedadataModel()
        self.assertEqual(medadata_model.url, '')

        utils.set_git_repo_metadata_from_path(medadata_model, path='.')
        self.assertIn(medadata_model.url, [
            'https://github.com/KarrLab/obj_model.git',
            'ssh://git@github.com/KarrLab/obj_model.git',
            'git@github.com:KarrLab/obj_model.git',
        ])

        class MedadataModel(core.Model):
            url = core.StringAttribute()
            branch = core.StringAttribute()
            commit_hash = core.StringAttribute()

        medadata_model = MedadataModel()
        utils.set_git_repo_metadata_from_path(medadata_model, path='.', commit_hash_attr='commit_hash')
        self.assertEqual(40, len(medadata_model.commit_hash))

    def test_set_git_repo_metadata_from_path_error(self):
        tempdir = tempfile.mkdtemp()

        medadata_model = self.MedadataModel()
        self.assertEqual(medadata_model.url, '')

        with self.assertRaisesRegex(ValueError, 'is not a Git repository'):
            utils.set_git_repo_metadata_from_path(medadata_model, path=tempdir)
        self.assertEqual(medadata_model.url, '')

        shutil.rmtree(tempdir)
