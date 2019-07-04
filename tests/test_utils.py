""" Data model to represent models.

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""
from six import string_types
import git
import os
import shutil
import sys
import tempfile
import unittest
from obj_model import core, utils
from obj_model.utils import DataRepoMetadata, SchemaRepoMetadata
from wc_utils.util.git import GitHubRepoForTests, RepoMetadataCollectionType


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
        self.assertEqual(utils.get_attribute_by_name(Root, None, None), (None, None))

        self.assertEqual(utils.get_attribute_by_name(Root, None, 'id'), (None, Root.Meta.attributes['id']))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'id2'), (None, None))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'Identifier', verbose_name=True), (None, Root.Meta.attributes['id']))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'Identifier2', verbose_name=True), (None, None))

        self.assertEqual(utils.get_attribute_by_name(Root, None, 'ID', case_insensitive=True), (None, Root.Meta.attributes['id']))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'ID', case_insensitive=False), (None, None))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'identifier', verbose_name=True,
                                                     case_insensitive=True), (None, Root.Meta.attributes['id']))
        self.assertEqual(utils.get_attribute_by_name(Root, None, 'identifier', verbose_name=True, case_insensitive=False), (None, None))

        class Parent(core.Model):
            quantity_1 = core.OneToOneAttribute('Quantity', related_name='parent_q_1')
            quantity_2 = core.OneToOneAttribute('Quantity', related_name='parent_q_2')
            value = core.FloatAttribute()
            units = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('quantity_1', 'quantity_2', 'value', 'units')

        class Quantity(core.Model):
            value = core.FloatAttribute()
            units = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('value', 'units')
                tabular_orientation = core.TabularOrientation.multiple_cells

            def serialize(self):
                return '{} {}'.format(value, units)

        self.assertEqual(utils.get_attribute_by_name(Parent, 'quantity_1', 'value'),
                         (Parent.Meta.attributes['quantity_1'], Quantity.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'quantity_1', 'units'),
                         (Parent.Meta.attributes['quantity_1'], Quantity.Meta.attributes['units']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'quantity_2', 'value'),
                         (Parent.Meta.attributes['quantity_2'], Quantity.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'quantity_2', 'units'),
                         (Parent.Meta.attributes['quantity_2'], Quantity.Meta.attributes['units']))
        self.assertEqual(utils.get_attribute_by_name(Parent, None, 'value'), (None, Parent.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, None, 'units'), (None, Parent.Meta.attributes['units']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'Quantity 1', 'Value', verbose_name=True),
                         (Parent.Meta.attributes['quantity_1'], Quantity.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'Quantity 1', 'Units', verbose_name=True),
                         (Parent.Meta.attributes['quantity_1'], Quantity.Meta.attributes['units']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'Quantity 2', 'Value', verbose_name=True),
                         (Parent.Meta.attributes['quantity_2'], Quantity.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, 'Quantity 2', 'Units', verbose_name=True),
                         (Parent.Meta.attributes['quantity_2'], Quantity.Meta.attributes['units']))
        self.assertEqual(utils.get_attribute_by_name(Parent, None, 'Value', verbose_name=True), (None, Parent.Meta.attributes['value']))
        self.assertEqual(utils.get_attribute_by_name(Parent, None, 'Units', verbose_name=True), (None, Parent.Meta.attributes['units']))

    def test_group_objects_by_model(self):
        (root, nodes, leaves) = (self.root, self.nodes, self.leaves)
        objects = [root] + nodes + leaves
        for grouped_objects in [
            utils.group_objects_by_model(objects),
            utils.group_objects_by_model(objects + nodes)]:
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


class TestMetadata(unittest.TestCase):

    def setUp(self):
        self.tmp_dirname = tempfile.mkdtemp()

        # prepare test data repo
        self.github_test_data_repo = GitHubRepoForTests('test_data_repo')
        self.test_data_repo_dir = os.path.join(self.tmp_dirname, 'test_data_repo')
        os.mkdir(self.test_data_repo_dir)
        self.test_data_repo = self.github_test_data_repo.make_test_repo(self.test_data_repo_dir)

        # prepare test schema repo
        test_schema_repo_url = 'https://github.com/KarrLab/test_repo'
        self.test_schema_repo_dir = os.path.join(self.tmp_dirname, 'test_schema_repo')
        test_schema_repo = git.Repo.clone_from(test_schema_repo_url, self.test_schema_repo_dir)

        # put schema dir on sys.path
        sys.path.append(self.test_schema_repo_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dirname)

        # clean up
        self.github_test_data_repo.delete_test_repo()

        # remove self.test_schema_repo_dir from sys.path
        for idx in range(len(sys.path)-1, -1, -1):
            if sys.path[idx] == self.test_schema_repo_dir:
                del sys.path[idx]

    def test_set_git_repo_metadata_from_path(self):

        # get & test git metadata
        path = os.path.join(self.test_data_repo_dir, 'test.xlsx')
        data_repo_metadata = DataRepoMetadata()
        unsuitable_changes = utils.set_git_repo_metadata_from_path(data_repo_metadata,
                                                                   RepoMetadataCollectionType.DATA_REPO,
                                                                   path=path)
        self.assertEqual(unsuitable_changes, [])
        self.assertEqual(data_repo_metadata.url, 'https://github.com/KarrLab/test_data_repo.git')
        self.assertEqual(data_repo_metadata.branch, 'master')
        self.assertTrue(isinstance(data_repo_metadata.revision, str))
        self.assertEqual(len(data_repo_metadata.revision), 40)

    def test_set_git_repo_metadata_from_path_error(self):

        data_repo_metadata = DataRepoMetadata()
        self.assertEqual(data_repo_metadata.url, '')

        with self.assertRaisesRegex(ValueError, 'is not in a Git repository'):
            utils.set_git_repo_metadata_from_path(data_repo_metadata,
                                                  RepoMetadataCollectionType.SCHEMA_REPO,
                                                  path=self.tmp_dirname)
        self.assertEqual(data_repo_metadata.url, '')

    def test_read_metadata_from_file(self):
        # use fixtures to keep this code simple
        # test .xlsx files
        metadata_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'metadata')
        expected_xlsx_metadata = {
            'both-metadata.xlsx': (DataRepoMetadata, SchemaRepoMetadata),
            'data-repo-metadata.xlsx': (DataRepoMetadata, type(None)),
            'no-metadata.xlsx': (type(None), type(None)),
            'schema-repo-metadata.xlsx': (type(None), SchemaRepoMetadata)
        }
        for filename, expected_metadata_types in expected_xlsx_metadata.items():
            pathname = os.path.join(metadata_dir, filename)
            data_file_metadata = utils.read_metadata_from_file(pathname)
            actual_data_file_metadata_types = \
                (type(data_file_metadata.data_repo_metadata), type(data_file_metadata.schema_repo_metadata))
            self.assertEqual(actual_data_file_metadata_types, expected_metadata_types)

        # test .csv file
        csv_pathname = os.path.join(metadata_dir, 'csv_metadata', 'test*.csv')
        data_file_metadata = utils.read_metadata_from_file(csv_pathname)
        self.assertTrue(isinstance(data_file_metadata.data_repo_metadata, DataRepoMetadata))
        self.assertTrue(isinstance(data_file_metadata.schema_repo_metadata, SchemaRepoMetadata))
        for metadata in data_file_metadata:
            self.assertTrue(metadata.url.startswith('https://github.com/'))
            self.assertEqual(metadata.branch, 'master')
            self.assertTrue(isinstance(metadata.revision, str))
            self.assertEqual(len(metadata.revision), 40)

        # test exceptions
        with self.assertRaisesRegex(ValueError, "Multiple instances of .+ found in"):
            pathname = os.path.join(metadata_dir, 'extra-schema-metadata.xlsx')
            utils.read_metadata_from_file(pathname)

    def test_add_metadata_to_file(self):
        class Model1(core.Model):
            id = core.SlugAttribute()

        metadata_dir = os.path.join(os.path.dirname(__file__), 'fixtures', 'metadata')
        shutil.copy(os.path.join(metadata_dir, 'no-metadata.xlsx'), self.test_data_repo_dir)
        pathname = os.path.join(self.test_data_repo_dir, 'no-metadata.xlsx')
        # self.test_data_repo.index.add([pathname])

        metadata_path = utils.add_metadata_to_file(pathname, [Model1], schema_package='test_repo')
        data_file_metadata = utils.read_metadata_from_file(metadata_path)
        self.assertTrue(isinstance(data_file_metadata.data_repo_metadata, DataRepoMetadata))
        self.assertTrue(isinstance(data_file_metadata.schema_repo_metadata, SchemaRepoMetadata))
        for metadata in data_file_metadata:
            self.assertTrue(metadata.url.startswith('https://github.com/'))
            self.assertEqual(metadata.branch, 'master')
            self.assertTrue(isinstance(metadata.revision, str))
            self.assertEqual(len(metadata.revision), 40)
