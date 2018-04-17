""" Test schema IO

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from os.path import splitext
from obj_model import core, utils
from obj_model.io import WorkbookReader, WorkbookWriter, convert, create_template, IoWarning
from wc_utils.workbook.io import (Workbook, Worksheet, Row, WorksheetStyle,
                                  read as read_workbook, get_reader, get_writer)
import enum
import math
import mock
import obj_model.io
import openpyxl
import os
import pytest
import re
import shutil
import sys
import tempfile
import unittest


class MainRoot(core.Model):
    id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
    name = core.StringAttribute()

    class Meta(core.Model.Meta):
        attribute_order = ('id', 'name', )
        tabular_orientation = core.TabularOrientation.column


class Node(core.Model):
    id = core.SlugAttribute(primary=True)
    root = core.ManyToOneAttribute(MainRoot, related_name='nodes')
    val1 = core.FloatAttribute()
    val2 = core.FloatAttribute()

    class Meta(core.Model.Meta):
        attribute_order = ('id', 'root', 'val1', 'val2', )
        indexed_attrs_tuples = (('id',), ('id', 'val1'))


class OneToManyRowAttribute(core.OneToManyAttribute):
    pass


class OneToManyInlineAttribute(core.OneToManyAttribute):

    def serialize(self, value):
        return ', '.join([obj.id for obj in value])

    def deserialize(self, value, objects):
        if value:
            objs = []
            for id in value.split(', '):
                obj = OneToManyInline(id=id)
                if OneToManyInline not in objects:
                    objects[OneToManyInline] = {}
                objects[OneToManyInline][id] = obj
                objs.append(obj)

            return (objs, None)
        else:
            return (set(), None)


class Leaf(core.Model):
    id = core.StringAttribute(primary=True)
    nodes = core.ManyToManyAttribute(Node, related_name='leaves')
    val1 = core.FloatAttribute()
    val2 = core.FloatAttribute()
    onetomany_rows = OneToManyRowAttribute('OneToManyRow', related_name='leaf', min_related_rev=1)
    onetomany_inlines = OneToManyInlineAttribute('OneToManyInline', related_name='leaf', min_related_rev=1)

    class Meta(core.Model.Meta):
        attribute_order = (
            'id', 'nodes', 'val1', 'val2',
            'onetomany_rows', 'onetomany_inlines'
        )


class OneToManyRow(core.Model):
    id = core.SlugAttribute(primary=True)

    class Meta(core.Model.Meta):
        attribute_order = ('id',)


class OneToManyInline(core.Model):
    id = core.SlugAttribute(primary=False)

    class Meta(core.Model.Meta):
        attribute_order = ('id',)
        tabular_orientation = core.TabularOrientation.inline


class TestIo(unittest.TestCase):

    def setUp(self):
        self.root = root = MainRoot(id='root', name=u'\u20ac')
        nodes = [
            Node(root=root, id='node_0', val1=1, val2=2),
            Node(root=root, id='node_1', val1=3, val2=4),
            Node(root=root, id='node_2', val1=5, val2=6),
        ]
        self.leaves = leaves = [
            Leaf(nodes=[nodes[0]], id='leaf_0_0', val1=7, val2=8),
            Leaf(nodes=[nodes[0]], id='leaf_0_1', val1=9, val2=10),
            Leaf(nodes=[nodes[1]], id='leaf_1_0', val1=11, val2=12),
            Leaf(nodes=[nodes[1]], id='leaf_1_1', val1=13, val2=14),
            Leaf(nodes=[nodes[2]], id='leaf_2_0', val1=15, val2=16),
            Leaf(nodes=[nodes[2]], id='leaf_2_1', val1=17, val2=18),
        ]
        leaves[0].onetomany_rows = [OneToManyRow(id='row_0_0'), OneToManyRow(id='row_0_1')]
        leaves[1].onetomany_rows = [OneToManyRow(id='row_1_0'), OneToManyRow(id='row_1_1')]
        leaves[2].onetomany_rows = [OneToManyRow(id='row_2_0'), OneToManyRow(id='row_2_1')]
        leaves[3].onetomany_rows = [OneToManyRow(id='row_3_0'), OneToManyRow(id='row_3_1')]
        leaves[4].onetomany_rows = [OneToManyRow(id='row_4_0'), OneToManyRow(id='row_4_1')]
        leaves[5].onetomany_rows = [OneToManyRow(id='row_5_0'), OneToManyRow(id='row_5_1')]

        leaves[0].onetomany_inlines = [OneToManyInline(id='inline_0_0'), OneToManyInline(id='inline_0_1')]
        leaves[1].onetomany_inlines = [OneToManyInline(id='inline_1_0'), OneToManyInline(id='inline_1_1')]
        leaves[2].onetomany_inlines = [OneToManyInline(id='inline_2_0'), OneToManyInline(id='inline_2_1')]
        leaves[3].onetomany_inlines = [OneToManyInline(id='inline_3_0'), OneToManyInline(id='inline_3_1')]
        leaves[4].onetomany_inlines = [OneToManyInline(id='inline_4_0'), OneToManyInline(id='inline_4_1')]
        leaves[5].onetomany_inlines = [OneToManyInline(id='inline_5_0'), OneToManyInline(id='inline_5_1')]

        self.tmp_dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dirname)

    def test_dummy_model(self):
        # test integrity of relationships
        for leaf in self.leaves:
            for row in leaf.onetomany_rows:
                self.assertEqual(row.leaf, leaf)

    def test_write_read(self):
        # write/read to/from Excel
        root = self.root
        objects = list(set([root] + root.get_related()))
        objects = utils.group_objects_by_model(objects)

        filename = os.path.join(self.tmp_dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [root], [MainRoot, Node, Leaf, ])
        WorkbookWriter().run(filename, root, [MainRoot, Node, Leaf, ])
        objects2 = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])

        # validate
        all_objects2 = []
        for model, model_objects in objects2.items():
            all_objects2.extend(model_objects)
        self.assertEqual(core.Validator().run(all_objects2), None)

        # test objects saved and loaded correctly
        for model in objects.keys():
            self.assertEqual(len(objects2[model]), len(objects[model]),
                             msg='Different numbers of "{}" objects'.format(model.__name__))
        self.assertEqual(len(objects2), len(objects))

        root2 = objects2[MainRoot].pop()

        filename2 = os.path.join(self.tmp_dirname, 'test2.xlsx')
        WorkbookWriter().run(filename2, [root2], [MainRoot, Node, Leaf, ])
        original = read_workbook(filename)
        copy = read_workbook(filename2)
        self.assertEqual(copy, original)

        self.assertEqual(set([x.id for x in root2.nodes]), set([x.id for x in root.nodes]))
        self.assertTrue(root2.is_equal(root))

        # unicode
        self.assertEqual(root2.name, u'\u20ac')

        #
        filename = os.path.join(self.tmp_dirname, 'test.xlsx')
        WorkbookWriter().run(filename, root, [MainRoot, Node, Leaf, ])

        WorkbookWriter().run(filename, None, [MainRoot, Node, Leaf, ])
        objects2 = WorkbookReader().run(filename, [MainRoot, Node, Leaf, ], group_objects_by_model=False)
        self.assertEqual(objects2, None)

    def test_manager(self):

        class Example0(core.Model):
            id = core.SlugAttribute(primary=True)
            int_attr = core.IntegerAttribute()

            class Meta(core.Model.Meta):
                indexed_attrs_tuples = (('id',),)
                attribute_order = ('id', 'int_attr')

        class Example1(core.Model):
            str_attr = core.StringAttribute()
            int_attr = core.IntegerAttribute()
            int_attr2 = core.IntegerAttribute()
            test0 = core.OneToOneAttribute(Example0, related_name='test1')

            class Meta(core.Model.Meta):
                indexed_attrs_tuples = (('str_attr',), ('int_attr', 'int_attr2'),)
                attribute_order = ('str_attr', 'int_attr', 'int_attr2', 'test0')

        filename = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_manager.xlsx')
        WorkbookReader().run(filename, [Example0, Example1])

        self.assertEqual(len(Example0.objects.get(id='A')), 1)
        self.assertEqual(len(Example1.objects.get(str_attr='C')), 2)
        self.assertEqual(len(Example1.objects.get(int_attr=11, int_attr2=21)), 1)
        self.assertEqual(Example0.objects.get_one(id='A'),
                         Example1.objects.get_one(int_attr=11, int_attr2=21).test0)
        with self.assertRaises(ValueError) as context:
            Example0.objects.get(int_attr=1)
        self.assertIn("not an indexed attribute tuple", str(context.exception))

    def test_read_inexact_worksheet_name_match(self):
        filename = os.path.join(self.tmp_dirname, 'test-*.csv')

        # write to file
        WorkbookWriter().run(filename, [self.root], [MainRoot, Node, Leaf, ])

        """ test reading worksheet by the model's name """
        # rename worksheet
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dirname, 'test-Main root.csv')))
        os.rename(os.path.join(self.tmp_dirname, 'test-Main root.csv'), os.path.join(self.tmp_dirname, 'test-MainRoot.csv'))

        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

        """ test reading worksheet by the model's verbose name """
        # rename worksheet
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dirname, 'test-Leaves.csv')))
        os.rename(os.path.join(self.tmp_dirname, 'test-Leaves.csv'), os.path.join(self.tmp_dirname, 'test-Leaf.csv'))

        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

        """ test reading worksheet by the model's plural verbose name """
        # rename worksheet
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dirname, 'test-MainRoot.csv')))
        os.rename(os.path.join(self.tmp_dirname, 'test-MainRoot.csv'), os.path.join(self.tmp_dirname, 'test-Main roots.csv'))

        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

        """ test reading worksheet by the model's plural verbose name, case-insensitive """
        # rename worksheet
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dirname, 'test-Main roots.csv')))
        os.rename(os.path.join(self.tmp_dirname, 'test-Main roots.csv'), os.path.join(self.tmp_dirname, 'test-main roots.csv'))

        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

    def test_read_inexact_attribute_name_match(self):
        filename = os.path.join(self.tmp_dirname, 'test.xlsx')
        filename2 = os.path.join(self.tmp_dirname, 'test2.xlsx')

        # write to file
        WorkbookWriter().run(filename, [self.root], [MainRoot, Node, Leaf, ])

        """ test reading attributes by verbose name """
        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

        """ test reading attributes by name """
        # setup reader, writer
        _, ext = splitext(filename)
        reader_cls = get_reader(ext)
        writer_cls = get_writer(ext)
        reader = reader_cls(filename)
        writer = writer_cls(filename2)

        # read workbook
        workbook = reader.run()

        # edit heading
        headings = workbook['Main root'][0]
        self.assertEqual(headings[0], 'Identifier')
        workbook['Main root'][0][0] = 'id'

        # write workbook
        writer.run(workbook)

        # check that attributes can be read by name
        objects = WorkbookReader().run(filename2, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

        """ test case insensitivity """
        # edit heading
        workbook['Main root'][0][0] = 'ID'

        # write workbook
        writer.run(workbook)

        # check that attributes can be read by name
        objects = WorkbookReader().run(filename2, [MainRoot, Node, Leaf, OneToManyRow])
        root = objects[MainRoot].pop()

        self.assertTrue(root.is_equal(self.root))

    def test_validation(self):
        t = MainRoot(name='f')
        self.assertIn('value for primary attribute cannot be empty',
                      t.validate().attributes[0].messages[0])

    def check_reader_errors(self, fixture_file, expected_messages, models, use_re=False,
                            do_not_catch=False):
        ''' Run WorkbookReader expecting an error; check that the exception message matches expected messages

        Args:
            fixture_file (:obj:`str`): name of the file to be read
            expected_messages (:obj:`list` of `str`): list of expected strings or patterns in the
                exception
            models (:obj:`list` of `Model`): `Model`s for the schema of the data being read
            use_re (:obj:`boolean`, optional): if set, `expected_messages` contains RE patterns
            do_not_catch (:obj:`boolean`, optional): if set, run WorkbookReader() outside try ... catch;
                produces full exception message for debugging

        Raises:
            :obj:`Exception`: if do_not_catch
        '''
        filename = os.path.join(os.path.dirname(__file__), 'fixtures', fixture_file)
        if do_not_catch:
            WorkbookReader().run(filename, models)
        with self.assertRaises(Exception) as context:
            WorkbookReader().run(filename, models)
        for msg in expected_messages:
            if not use_re:
                msg = re.escape(msg)
            self.assertRegexpMatches(str(context.exception), msg)

    def test_location_of_attrs(self):
        class Normal(core.Model):
            id = core.SlugAttribute()
            val = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'val')

        class Transposed(core.Model):
            tid = core.SlugAttribute()
            s = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('tid', 's', )
                tabular_orientation = core.TabularOrientation.column

        file = 'test-locations.xlsx'
        filename = os.path.join(os.path.dirname(__file__), 'fixtures', file)
        models = WorkbookReader().run(filename, [Normal, Transposed])
        ext = 'xlsx'
        normals = models[Normal]
        for obj in normals:
            if obj.val == 'x':
                (file_type, basename, worksheet, row, column) = obj.get_source('val')
                self.assertEqual(file_type, ext)
                self.assertEqual(basename, file)
                self.assertEqual(worksheet, obj.Meta.verbose_name_plural)
                self.assertEqual(row, 3)
                self.assertEqual(column, 'B')
                self.assertEqual(utils.source_report(obj, 'val'),
                                 ':'.join([file, obj.Meta.verbose_name_plural, "{}{}".format(column, row)]))

        transposeds = models[Transposed]
        for obj in transposeds:
            if obj.s == 'z':
                (file_type, basename, worksheet, row, column) = obj.get_source('s')
                self.assertEqual(file_type, ext)
                self.assertEqual(basename, file)
                self.assertEqual(worksheet, obj.Meta.verbose_name)
                self.assertEqual(row, 2)
                self.assertEqual(column, 'C')
                self.assertEqual(utils.source_report(obj, 's'),
                                 ':'.join([file, obj.Meta.verbose_name, "{}{}".format(column, row)]))

        file = 'test-locations-*.csv'
        filename = os.path.join(os.path.dirname(__file__), 'fixtures', file)
        models = WorkbookReader().run(filename, [Normal, Transposed])
        ext = 'csv'
        normals = models[Normal]
        for obj in normals:
            if obj.val == 'x':
                (file_type, basename, worksheet, row, column) = obj.get_source('val')
                self.assertEqual(file_type, ext)
                self.assertEqual(basename, file)
                self.assertEqual(row, 3)
                self.assertEqual(worksheet, obj.Meta.verbose_name_plural)
                self.assertEqual(column, 2)
                self.assertEqual(utils.source_report(obj, 'val'),
                                 ':'.join([file, obj.Meta.verbose_name_plural, "{},{}".format(row, column)]))

        transposeds = models[Transposed]
        for obj in transposeds:
            if obj.s == 'z':
                (file_type, basename, worksheet, row, column) = obj.get_source('s')
                self.assertEqual(file_type, ext)
                self.assertEqual(basename, file)
                self.assertEqual(worksheet, obj.Meta.verbose_name)
                self.assertEqual(row, 2)
                self.assertEqual(column, 3)
                self.assertEqual(utils.source_report(obj, 's'),
                                 ':'.join([file, obj.Meta.verbose_name, "{},{}".format(row, column)]))

    def test_read_bad_headers(self):
        msgs = [
            "The model cannot be loaded because 'bad-headers.xlsx' contains error(s)",
            "Empty header field in row 1, col E - delete empty column(s)",
            "Header 'y' in row 1, col F does not match any attribute",
            "Empty header field in row 3, col A - delete empty row(s)",
        ]
        self.check_reader_errors('bad-headers.xlsx', msgs, [MainRoot, Node, Leaf, OneToManyRow])

        msgs = [
            "The model cannot be loaded because 'bad-headers-*.csv' contains error(s)",
            "Header 'x' in row 5, col 1 does not match any attribute",
            "Empty header field in row 1, col 5 - delete empty column(s)",
        ]
        self.check_reader_errors('bad-headers-*.csv', msgs, [MainRoot, Node, Leaf, OneToManyRow])

        '''
        msgs = [
            "Duplicate, case insensitive, header fields: 'MainRoot', 'root'",
            "Duplicate, case insensitive, header fields: 'good val', 'Good val', 'Good VAL'"]
        self.check_reader_errors('duplicate-headers.xlsx', msgs, [Node])
        '''

    def test_uncaught_data_error(self):
        class Test(core.Model):
            id = core.SlugAttribute(primary=True)
            float1 = core.FloatAttribute()
            bool1 = core.FloatAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'float1', 'bool1', )

        msgs = ["The model cannot be loaded because 'uncaught-error.xlsx' contains error(s)",
                "uncaught-error.xlsx:Tests:B5",
                "uncaught-error.xlsx:Tests:C6",
                "Value must be an instance of `float`",
                ]
        self.check_reader_errors('uncaught-error.xlsx', msgs, [MainRoot, Test])

    def test_read_invalid_data(self):
        class NormalRecord(core.Model):
            id_with_underscores = core.SlugAttribute()
            val = core.StringAttribute(min_length=2)

            class Meta(core.Model.Meta):
                attribute_order = ('id_with_underscores', 'val')

        class Transposed(core.Model):
            id = core.SlugAttribute()
            val = core.StringAttribute(min_length=2)

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'val', )
                tabular_orientation = core.TabularOrientation.column

        RE_msgs = [
            "Leaf\n +'id':''\n +invalid-data.xlsx:Leaves:A6\n +StringAttribute value for primary "
            "attribute cannot be empty",
            "invalid-data.xlsx:'Normal records':B3",
            "Transposed\n +'val':'x'\n +invalid-data.xlsx:Transposed:C2\n +Value must be at least "
            "2 characters",
        ]
        self.check_reader_errors('invalid-data.xlsx', RE_msgs, [Leaf, NormalRecord, Transposed],
                                 use_re=True)

        RE_msgs = [
            "The model cannot be loaded because 'invalid-data-\*.csv' contains error",
            "Leaf *\n +'id':''\n +invalid-data-\*.csv:Leaves:6,1\n +StringAttribute value for "
            "primary attribute cannot be empty",
            "Transposed\n +'val':'x'\n +invalid-data-\*.csv:Transposed:2,3\n +Value must be at "
            "least 2 characters",
        ]
        self.check_reader_errors('invalid-data-*.csv', RE_msgs, [Leaf, NormalRecord, Transposed],
                                 use_re=True)

    def test_reference_errors(self):
        class NodeFriend(core.Model):
            id = core.SlugAttribute()
            node = core.OneToOneAttribute(Node, related_name='nodes')
            val = core.StringAttribute(min_length=2)

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'node', 'val')

        RE_msgs = [
            "reference-errors.xlsx:Nodes:B3\n +Unable to find MainRoot with id='not root'",
            "reference-errors.xlsx:Leaves:B6\n +Unable to find Node with id='no such node'",
            "reference-errors.xlsx:Leaves:E7\n +Unable to find OneToManyRow with id='no such row'",
            "reference-errors.xlsx:'Node friends':B2\n +Unable to find Node with id=no_node",
        ]
        self.check_reader_errors('reference-errors.xlsx', RE_msgs,
                                 [MainRoot, Node, NodeFriend, Leaf, OneToManyRow], use_re=True)

    def test_duplicate_primaries(self):
        RE_msgs = [
            "The model cannot be loaded because it fails to validate",
            "Node:\n +'id':\n +id values must be unique, but these values are repeated: node_2",
            "MainRoot:\n +'id':\n +id values must be unique, but these values are repeated: 'root 2'",
        ]
        self.check_reader_errors('duplicate-primaries.xlsx', RE_msgs, [MainRoot, Node, Leaf, OneToManyRow],
                                 use_re=True)

    def test_create_worksheet_style(self):
        self.assertIsInstance(WorkbookWriter.create_worksheet_style(MainRoot), WorksheetStyle)

    def test_convert(self):
        filename_xls1 = os.path.join(self.tmp_dirname, 'test1.xlsx')
        filename_xls2 = os.path.join(self.tmp_dirname, 'test2.xlsx')
        filename_csv = os.path.join(self.tmp_dirname, 'test-*.csv')

        models = [MainRoot, Node, Leaf, OneToManyRow]

        WorkbookWriter().run(filename_xls1, [self.root], models)

        convert(filename_xls1, filename_csv, models)
        convert(filename_csv, filename_xls2, models)

        objects2 = WorkbookReader().run(filename_csv, models)
        self.assertTrue(self.root.is_equal(objects2[MainRoot][0]))

        objects2 = WorkbookReader().run(filename_xls2, models)
        self.assertTrue(self.root.is_equal(objects2[MainRoot][0]))

    def test_create_template(self):
        filename = os.path.join(self.tmp_dirname, 'test3.xlsx')
        create_template(filename, [MainRoot, Node, Leaf])
        objects = WorkbookReader().run(filename, [MainRoot, Node, Leaf])
        self.assertEqual(objects, {
            MainRoot: [],
            Node: [],
            Leaf: [],
        })
        self.assertEqual(core.Validator().run([]), None)

    def run_options_helper(self, fixture_file):
        filename = os.path.join(os.path.dirname(__file__), 'fixtures', fixture_file)

        class SimpleModel(core.Model):
            val = core.StringAttribute(min_length=10)

        with self.assertRaises(ValueError) as context:
            # raises extra sheet exception
            WorkbookReader().run(filename, [SimpleModel])
        self.assertEqual(str(context.exception),
                         "No matching models for worksheets/files {} / extra sheet".format(fixture_file))

        with self.assertRaises(ValueError) as context:
            # raises extra attribute exception
            WorkbookReader().run(filename, [SimpleModel], ignore_extra_sheets=True)
        self.assertRegexpMatches(str(context.exception),
                                 "The model cannot be loaded because 'test_run_options.*' contains error.*")
        if 'xlsx' in fixture_file:
            col = 'B'
        elif 'csv' in fixture_file:
            col = '2'
        self.assertRegexpMatches(str(context.exception),
                                 ".*Header 'extra' in row 1, col {} does not match any attribute.*".format(col))

        with self.assertRaises(ValueError) as context:
            # raises validation exception on 'too short'
            WorkbookReader().run(filename, [SimpleModel], ignore_extra_sheets=True,
                                 ignore_extra_attributes=True)
        self.assertRegexpMatches(str(context.exception),
                                 "The model cannot be loaded because 'test_run_options.*' contains error.*")
        if 'xlsx' in fixture_file:
            location = 'A3'
        elif 'csv' in fixture_file:
            location = '3,1'
        self.assertRegexpMatches(str(context.exception),
                                 ".*'val':'too short'\n.*test_run_options.*:'Simple models':{}\n.*"
                                 "Value must be at least 10 characters".format(location))

        class SimpleModel(core.Model):
            val = core.StringAttribute()
        model = WorkbookReader().run(filename, [SimpleModel], ignore_extra_sheets=True,
                                     ignore_extra_attributes=True)
        self.assertIn('too short', [r.val for r in model[SimpleModel]])

    def test_run_options(self):
        self.run_options_helper('test_run_options.xlsx')
        self.run_options_helper('test_run_options-*.csv')

    def test_get_ambiguous_sheet_names(self):
        class TestModel(core.Model):
            pass

        class TestModels(core.Model):
            pass

        class TestModels2(core.Model):
            pass

        class TestModels3(core.Model):

            class Meta(core.Model.Meta):
                verbose_name = 'TestModel'

        self.assertEqual(sorted(WorkbookReader.get_possible_model_sheet_names(TestModel)),
                         sorted(['TestModel', 'Test model', 'Test models']))
        self.assertEqual(sorted(WorkbookReader.get_possible_model_sheet_names(TestModels)),
                         sorted(['TestModels', 'Test models', 'Test modelss']))
        self.assertEqual(sorted(WorkbookReader.get_possible_model_sheet_names(TestModels2)),
                         sorted(['TestModels2', 'Test models2', 'Test models2s']))
        self.assertEqual(sorted(WorkbookReader.get_possible_model_sheet_names(TestModels3)),
                         sorted(['TestModels3', 'TestModel', 'TestModels']))

        ambiguous_sheet_names = WorkbookReader.get_ambiguous_sheet_names(['Test models', 'Test model', 'TestModel', 'TestModels'], [
            TestModel, TestModels, TestModels2, TestModels3])
        self.assertEqual(len(ambiguous_sheet_names), 3)
        self.assertEqual(ambiguous_sheet_names['Test models'], [TestModel, TestModels])
        self.assertEqual(ambiguous_sheet_names['TestModel'], [TestModel, TestModels3])
        self.assertEqual(ambiguous_sheet_names['TestModels'], [TestModels, TestModels3])

    def test_read_empty_numeric_cell(self):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet('Test models')

        cell = ws.cell(row=1, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Id'

        cell = ws.cell(row=1, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Value'

        cell = ws.cell(row=2, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-1'

        cell = ws.cell(row=2, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_NUMERIC
        cell.value = 2.

        cell = ws.cell(row=3, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-2'

        cell = ws.cell(row=3, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_NUMERIC
        cell.value = 3.

        cell = ws.cell(row=4, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-3'

        cell = ws.cell(row=4, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_NUMERIC
        cell.value = None

        cell = ws.cell(row=5, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-4'

        cell = ws.cell(row=5, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = None

        cell = ws.cell(row=6, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-5'

        cell = ws.cell(row=6, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = ''

        cell = ws.cell(row=7, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-6'

        cell = ws.cell(row=7, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_NULL
        cell.value = None

        cell = ws.cell(row=8, column=1)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_STRING
        cell.value = 'Model-7'

        cell = ws.cell(row=8, column=2)
        cell.data_type = openpyxl.cell.cell.Cell.TYPE_NUMERIC
        cell.value = 5.

        filename = os.path.join(self.tmp_dirname, 'test.xlsx')
        wb.save(filename)

        class TestModel(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            value = core.FloatAttribute()

        models = WorkbookReader().run(filename, [TestModel])[TestModel]
        models.sort(key=lambda model: model.id)

        m = TestModel.objects.get_one(id='Model-2')
        self.assertEqual(models[0].value, 2.)
        self.assertEqual(models[1].value, 3.)
        self.assertTrue(math.isnan(models[2].value))
        self.assertTrue(math.isnan(models[3].value))
        self.assertTrue(math.isnan(models[4].value))
        self.assertTrue(math.isnan(models[5].value))
        self.assertEqual(models[6].value, 5.)

    def test_not_existant_referenced_object(self):
        class ErrorAttribute(core.StringAttribute):
            def deserialize(self, value):
                raise Exception()

        class TestModel(core.Model):
            id = ErrorAttribute(primary=True, unique=True)

        workbook = Workbook()

        workbook['Test models'] = worksheet = Worksheet()
        worksheet.append(Row(['Id']))
        worksheet.append(Row(['A']))
        worksheet.append(Row(['B']))
        worksheet.append(Row(['C']))

        filename = os.path.join(self.tmp_dirname, 'test.xlsx')
        xslx_writer = get_writer('.xlsx')(filename)
        xslx_writer.run(workbook)

        with self.assertRaisesRegexp(ValueError, 'The model cannot be loaded'):
            WorkbookReader().run(filename, [TestModel])


class TestMisc(unittest.TestCase):

    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_read_write_row_oriented(self):
        class Parent1(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
            children = core.OneToManyAttribute('Child1', verbose_name='children', related_name='parent')

        class Child1(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

        parents = [
            Parent1(id='parent_0'),
            Parent1(id='parent_1'),
            Parent1(id='parent_2'),
        ]
        parents[0].children.create(id='child_0_0')
        parents[0].children.create(id='child_0_1')
        parents[0].children.create(id='child_0_2')
        parents[1].children.create(id='child_1_0')
        parents[1].children.create(id='child_1_1')
        parents[1].children.create(id='child_1_2')
        parents[2].children.create(id='child_2_0')
        parents[2].children.create(id='child_2_1')
        parents[2].children.create(id='child_2_2')

        filename = os.path.join(self.dirname, 'test.xlsx')

        writer = WorkbookWriter()
        writer.run(filename, parents, [Parent1, Child1])

        objects = WorkbookReader().run(filename, [Parent1, Child1])
        objects[Parent1].sort(key=lambda parent: parent.id)
        for orig_parent, copy_parent in zip(parents, objects[Parent1]):
            self.assertTrue(orig_parent.is_equal(copy_parent))

    def test_warn_about_errors(self):
        class Node2(core.Model):
            id = core.StringAttribute(max_length=1, primary=True, unique=True, verbose_name='Identifier')

        node = Node2(id='id')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()

        with pytest.warns(IoWarning):
            writer.run(filename, [node], [Node2])

    def test_writer_error_if_not_serializable(self):
        class ChildrenAttribute3(core.OneToManyAttribute):
            pass

        class Parent3(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
            children = ChildrenAttribute3('Child3', verbose_name='children', related_name='parent')

        class Child3(core.Model):
            id = core.StringAttribute(verbose_name='Identifier')

        parent = Parent3(id='parent')
        parent.children.create(id='child_1')
        parent.children.create(id='child_2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()

        with self.assertRaisesRegexp(ValueError, 'cannot be serialized'):
            writer.run(filename, [parent], [Parent3, Child3])

    def test_reader_error_if_not_serializable(self):
        class WriterChildrenAttribute(core.OneToManyAttribute):
            def serialize(self, value):
                return super(WriterChildrenAttribute, self).serialize(value)

            def deserialize(self, values, objects):
                return super(WriterChildrenAttribute, self).deserialize(value, objects)

        class WriterParent(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
            children = WriterChildrenAttribute('WriterChild', verbose_name='children', related_name='parent')

            class Meta(core.Model.Meta):
                verbose_name_plural = 'Parents'

        class WriterChild(core.Model):
            id = core.StringAttribute(primary=True, verbose_name='Identifier')

            class Meta(core.Model.Meta):
                verbose_name_plural = 'Children'

        class ReaderChildrenAttribute(core.OneToManyAttribute):
            pass

        class ReaderParent(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
            children = ReaderChildrenAttribute('ReaderChild', verbose_name='children', related_name='parent')

            class Meta(core.Model.Meta):
                verbose_name_plural = 'Parents'

        class ReaderChild(core.Model):
            id = core.StringAttribute(verbose_name='Identifier')

            class Meta(core.Model.Meta):
                verbose_name_plural = 'Children'

        parent = WriterParent(id='parent')
        parent.children.create(id='child_1')
        parent.children.create(id='child_2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()
        writer.run(filename, [parent], [WriterParent, WriterChild])

        with self.assertRaisesRegexp(ValueError, 'cannot be serialized'):
            WorkbookReader().run(filename, [ReaderParent, ReaderChild])

    def test_abiguous_sheet_names_error(self):
        class Node4(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

            class Meta(core.Model.Meta):
                verbose_name = 'Node'

        class Node5(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

            class Meta(core.Model.Meta):
                verbose_name = 'Node'

        node1 = Node4(id='node_1')
        node2 = Node5(id='node_2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()

        with pytest.warns(IoWarning):
            writer.run(filename, [node1, node2], [Node4, Node5])

        with self.assertRaisesRegexp(ValueError, 'The following sheets cannot be unambiguously mapped to models:'):
            WorkbookReader().run(filename, [Node4, Node5])

    def test_read_missing_sheet(self):
        class Node6(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

        class Node7(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

        nodes = [
            Node6(id='node_6_0'),
            Node6(id='node_6_1'),
            Node6(id='node_6_2'),
        ]

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()
        writer.run(filename, nodes, [Node6])

        objects = WorkbookReader().run(filename, [Node6, Node7], ignore_missing_sheets=True)
        objects[Node6].sort(key=lambda node: node.id)
        for orig_node, copy_node in zip(nodes, objects[Node6]):
            self.assertTrue(orig_node.is_equal(copy_node))
        self.assertEqual(objects[Node7], [])

    def test_ambiguous_column_headers(self):
        class Node8(core.Model):
            id1 = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')
            id2 = core.StringAttribute(primary=False, unique=True, verbose_name='Identifier')
            id3 = core.StringAttribute(primary=False, unique=True)

        nodes = [
            Node8(id1='node_0_1', id2='node_0_2'),
            Node8(id1='node_1_1', id2='node_1_2'),
        ]

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()

        with pytest.warns(IoWarning):
            writer.run(filename, nodes, [Node8])

        with self.assertRaisesRegexp(ValueError, 'Duplicate, case insensitive, header fields:'):
            WorkbookReader().run(filename, [Node8])

    def test_row_and_column_headings(self):
        filename = os.path.join(self.dirname, 'test.xlsx')
        writer = WorkbookWriter()
        xslx_writer = get_writer('.xlsx')(filename)
        xslx_writer.initialize_workbook()
        writer.write_sheet(xslx_writer,
                           sheet_name='Sheet',
                           data=[['Cell_2_B', 'Cell_2_C'], ['Cell_3_B', 'Cell_3_C']],
                           row_headings=[['Row_2', 'Row_3']],
                           column_headings=[['Column_B', 'Column_C']])
        xslx_writer.finalize_workbook()

        xlsx_reader = get_reader('.xlsx')(filename)
        workbook = xlsx_reader.run()
        self.assertEqual(list(workbook['Sheet'][0]), [None, 'Column_B', 'Column_C'])
        self.assertEqual(list(workbook['Sheet'][1]), ['Row_2', 'Cell_2_B', 'Cell_2_C'])
        self.assertEqual(list(workbook['Sheet'][2]), ['Row_3', 'Cell_3_B', 'Cell_3_C'])

        reader = WorkbookReader()
        xlsx_reader = get_reader('.xlsx')(filename)
        xlsx_reader.initialize_workbook()
        data, row_headings, column_headings = reader.read_sheet(xlsx_reader, 'Sheet',
                                                                num_row_heading_columns=1,
                                                                num_column_heading_rows=1)
        self.assertEqual(len(data), 2)
        self.assertEqual(list(data[0]), ['Cell_2_B', 'Cell_2_C'])
        self.assertEqual(list(data[1]), ['Cell_3_B', 'Cell_3_C'])
        self.assertEqual(row_headings, [['Row_2', 'Row_3']])
        self.assertEqual(len(column_headings), 1)
        self.assertEqual(list(column_headings[0]), ['Column_B', 'Column_C'])

    def test_get_model_sheet_name_error(self):
        class Node9(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Identifier')

            class Meta(core.Model.Meta):
                verbose_name_plural = 'Nodes'

        with self.assertRaisesRegexp(ValueError, 'matches multiple sheets'):
            WorkbookReader.get_model_sheet_name(['Nodes', 'nodes'], Node9)

    def test_unclean_data(self):
        workbook = Workbook()
        workbook['Node10'] = worksheet = Worksheet()
        worksheet.append(Row(['Id', 'Value']))
        worksheet.append(Row(['A', '1.0']))
        worksheet.append(Row(['B', 'x']))

        filename = os.path.join(self.dirname, 'test.xlsx')
        xslx_writer = get_writer('.xlsx')(filename)
        xslx_writer.run(workbook)

        class Node10(core.Model):
            id = core.StringAttribute(primary=True, unique=True, verbose_name='Id')
            value = core.FloatAttribute(verbose_name='Value')

        with self.assertRaisesRegexp(ValueError, 'Value must be a `float`'):
            WorkbookReader().run(filename, [Node10])


class ReadEmptyCellTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_clean_enum(self):
        class TestEnum(enum.Enum):
            val = 0

        attr = core.EnumAttribute(TestEnum)
        self.assertNotEqual(attr.clean({})[1], None)

    def test_get_default_cleaned_value(self):
        class ConcreteAttribute(core.Attribute):
            def deserialize(self):
                pass

            def serialize(self):
                pass

            def validate(self):
                pass

            def to_json(self, encoded=None):
                pass

            def from_json(self, json, decoded=None):
                pass

        attr = ConcreteAttribute(default_cleaned_value=lambda: 1.5)
        self.assertEqual(attr.get_default_cleaned_value(), 1.5)

    def test_read_empty_float(self):
        class TestModel(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            value_1 = core.FloatAttribute(default_cleaned_value=float('nan'))
            value_2 = core.FloatAttribute(default_cleaned_value=2.)

        workbook = Workbook()
        workbook['Test models'] = worksheet = Worksheet()
        worksheet.append(Row(['Id', 'Value 1', 'Value 2']))
        worksheet.append(Row(['A', None, None]))
        worksheet.append(Row(['B', 1., 3.]))
        worksheet.append(Row(['C', None, None]))

        filename = os.path.join(self.dirname, 'test.xlsx')
        xslx_writer = get_writer('.xlsx')(filename)
        xslx_writer.run(workbook)

        objects = WorkbookReader().run(filename, [TestModel])[TestModel]
        objects.sort(key=lambda m: m.id)

        self.assertTrue(math.isnan(objects[0].value_1))
        self.assertEqual(objects[1].value_1, 1.)
        self.assertTrue(math.isnan(objects[2].value_1))

        self.assertEqual(objects[0].value_2, 2.)
        self.assertEqual(objects[1].value_2, 3.)
        self.assertEqual(objects[2].value_2, 2.)


class InheritedIoTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_OneToOneAttribute(self):
        class B(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class BB(B):
            pass

        class A(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            b = core.OneToOneAttribute(B, related_name='a')

        class AA(A):
            pass

        aa1 = AA(id='aa1')
        bb1 = BB(id='bb')
        aa1.b = bb1

        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [aa1], [AA, BB])

        aa2 = WorkbookReader().run(filename, [AA, BB])[AA][0]
        self.assertTrue(aa2.is_equal(aa1))
        self.assertEqual(aa1.b.a, aa1)

    def test_ManyToOneAttribute(self):
        class B(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class BB(B):
            pass

        class A(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            b = core.ManyToOneAttribute(B, related_name='a_s')

        class AA(A):
            pass

        aa1 = AA(id='aa1')
        bb1 = BB(id='bb')
        aa1.b = bb1

        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [aa1], [AA, BB])

        aa2 = WorkbookReader().run(filename, [AA, BB])[AA][0]
        self.assertTrue(aa2.is_equal(aa1))
        self.assertIn(aa1, aa1.b.a_s)

    def test_OneToManyAttribute(self):
        class B(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class BB(B):
            pass

        class A(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            bs = core.OneToManyAttribute(B, related_name='a')

        class AA(A):
            pass

        aa1 = AA(id='aa1')
        bb1 = BB(id='bb')
        aa1.bs.append(bb1)

        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [aa1], [AA, BB])

        aa2 = WorkbookReader().run(filename, [AA, BB])[AA][0]
        self.assertTrue(aa2.is_equal(aa1))
        self.assertEqual(bb1.a, aa1)

    def test_ManyToManyAttribute(self):
        class B(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class BB(B):
            pass

        class A(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            bs = core.ManyToManyAttribute(B, related_name='a_s')

        class AA(A):
            pass

        aa1 = AA(id='aa1')
        bb1 = BB(id='bb')
        aa1.bs.append(bb1)

        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [aa1], [AA, BB])

        aa2 = WorkbookReader().run(filename, [AA, BB])[AA][0]
        self.assertTrue(aa2.is_equal(aa1))
        self.assertIn(aa1, bb1.a_s)


class StrictReadingTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_missing_sheet(self):
        class Model1(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class Model2(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
        m1 = Model1(id='m1')
        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [m1], [Model1])

        result = WorkbookReader().run(filename, [Model1])
        self.assertEqual(set(result.keys()), set([Model1]))
        self.assertEqual(len(result[Model1]), 1)
        self.assertTrue(m1.is_equal(result[Model1][0]))

        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model1, Model2])

        result = WorkbookReader().run(filename, [Model1, Model2], ignore_missing_sheets=True)
        self.assertEqual(set(result.keys()), set([Model1, Model2]))
        self.assertEqual(len(result[Model1]), 1)
        self.assertEqual(len(result[Model2]), 0)
        self.assertTrue(m1.is_equal(result[Model1][0]))

    def test_extra_sheet(self):
        class Model1(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class Model2(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
        m1 = Model1(id='m1')
        m2 = Model2(id='m2')
        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [m1, m2], [Model1, Model2])

        result = WorkbookReader().run(filename, [Model1, Model2])
        self.assertEqual(set(result.keys()), set([Model1, Model2]))
        self.assertEqual(len(result[Model1]), 1)
        self.assertEqual(len(result[Model2]), 1)
        self.assertTrue(m1.is_equal(result[Model1][0]))
        self.assertTrue(m2.is_equal(result[Model2][0]))

        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model1])

        result = WorkbookReader().run(filename, [Model1], ignore_extra_sheets=True)
        self.assertEqual(set(result.keys()), set([Model1]))
        self.assertEqual(len(result[Model1]), 1)
        self.assertTrue(m1.is_equal(result[Model1][0]))

    def test_different_sheet_order(self):
        class Model1(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class Model2(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

        class Model3(core.Model):
            id = core.StringAttribute(primary=True, unique=True)

            class Meta(core.Model.Meta):
                tabular_orientation = core.TabularOrientation.column

        m1 = Model1(id='m1')
        m2 = Model2(id='m2')
        filename = os.path.join(self.dirname, 'test.xlsx')
        WorkbookWriter().run(filename, [m1, m2], [Model1, Model2])

        WorkbookReader().run(filename, [Model1, Model2])
        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model2, Model1])
        WorkbookReader().run(filename, [Model2, Model1], ignore_sheet_order=True)

        WorkbookWriter().run(filename, [m1], [Model1])
        WorkbookReader().run(filename, [Model1, Model3], ignore_missing_sheets=True)

    def test_missing_attribute(self):
        class Model(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            attr1 = core.StringAttribute()
            attr2 = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'attr1', 'attr2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer_cls = get_writer('.xlsx')
        writer = writer_cls(filename)

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr1', 'Attr2']))
        ws.append(Row(['m1', '1', '2']))
        writer.run(wb)
        WorkbookReader().run(filename, [Model])

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr2']))
        ws.append(Row(['m1', '2']))
        writer.run(wb)
        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model])
        WorkbookReader().run(filename, [Model], ignore_missing_attributes=True)

    def test_extra_attribute(self):
        class Model(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            attr1 = core.StringAttribute()
            attr2 = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'attr1', 'attr2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer_cls = get_writer('.xlsx')
        writer = writer_cls(filename)

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr1', 'Attr2']))
        ws.append(Row(['m1', '1', '2']))
        writer.run(wb)
        WorkbookReader().run(filename, [Model])

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr1', 'Attr2', 'Attr3']))
        ws.append(Row(['m1', '1', '2', '3']))
        writer.run(wb)
        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model])
        WorkbookReader().run(filename, [Model], ignore_extra_attributes=True)

    def test_different_attribute_order(self):
        class Model(core.Model):
            id = core.StringAttribute(primary=True, unique=True)
            attr1 = core.StringAttribute()
            attr2 = core.StringAttribute()

            class Meta(core.Model.Meta):
                attribute_order = ('id', 'attr1', 'attr2')

        filename = os.path.join(self.dirname, 'test.xlsx')
        writer_cls = get_writer('.xlsx')
        writer = writer_cls(filename)

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr1', 'Attr2']))
        ws.append(Row(['m1', '1', '2']))
        writer.run(wb)
        WorkbookReader().run(filename, [Model])

        wb = Workbook()
        wb['Models'] = ws = Worksheet()
        ws.append(Row(['Id', 'Attr2', 'Attr1']))
        ws.append(Row(['m1', '2', '1']))
        writer.run(wb)
        with self.assertRaises(ValueError):
            WorkbookReader().run(filename, [Model])
        WorkbookReader().run(filename, [Model], ignore_attribute_order=True)


class JsonTestCase(unittest.TestCase):
    def setUp(self):
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirname)

    def test_write_read(self):
        class AA(core.Model):
            id = core.StringAttribute()

        class BB(core.Model):
            id = core.StringAttribute()
            aa = core.ManyToOneAttribute(AA, related_name='bbs')

        class CC(core.Model):
            id = core.StringAttribute()
            bbs = core.ManyToOneAttribute(BB, related_name='ccs')
            aas = core.ManyToOneAttribute(AA, related_name='ccs')

        aa_0 = AA(id='aa_0')
        aa_1 = AA(id='aa_1')
        aa_2 = AA(id='aa_2')

        bb_0_0 = aa_0.bbs.create(id='bb_0_0')
        bb_0_1 = aa_0.bbs.create(id='bb_0_1')

        cc_0_0_0 = bb_0_0.ccs.create(id='cc_0_0_0')
        cc_0_0_1 = bb_0_0.ccs.create(id='cc_0_0_1')
        cc_0_1_0 = bb_0_1.ccs.create(id='cc_0_1_0')
        cc_0_1_1 = bb_0_1.ccs.create(id='cc_0_1_1')

        # todo
        #cc_0_0_0.aas = [aa_0]
        #cc_0_0_1.aas = [aa_1, aa_2]
        cc_0_0_0.aas = aa_0
        cc_0_0_1.aas = aa_1

        path = os.path.join(self.dirname, 'out.json')
        obj_model.io.JsonWriter().run(path, aa_0)
        aa_0_2 = obj_model.io.JsonReader().run(path, [AA])
        self.assertTrue(aa_0.is_equal(aa_0_2))

        obj_model.io.JsonWriter().run(path, [aa_0, aa_1], models=AA)
        aas = obj_model.io.JsonReader().run(path, [AA])
        self.assertEqual(len(aas), 2)
        self.assertTrue(aa_0.is_equal(aas[0]))
        self.assertTrue(aa_1.is_equal(aas[1]))

        obj_model.io.JsonWriter().run(path, aa_0, models=AA)
        aa_0_2 = obj_model.io.JsonReader().run(path, models=AA)
        self.assertTrue(aa_0.is_equal(aa_0_2))

        obj_model.io.JsonWriter().run(path, aa_0)
        aa_0_2 = obj_model.io.JsonReader().run(path, models=AA)
        self.assertTrue(aa_0.is_equal(aa_0_2))
        aa_0_2 = obj_model.io.JsonReader().run(path, models=AA, group_objects_by_model=True)
        self.assertEqual(list(aa_0_2.keys()), [AA])
        self.assertEqual(len(aa_0_2[AA]), 1)
        self.assertTrue(aa_0.is_equal(aa_0_2[AA][0]))

        obj_model.io.JsonWriter().run(path, None)
        self.assertEqual(obj_model.io.JsonReader().run(path), None)
        self.assertEqual(obj_model.io.JsonReader().run(path, models=AA, group_objects_by_model=True), {})

        path = os.path.join(self.dirname, 'out.yml')
        obj_model.io.JsonWriter().run(path, aa_0)
        aa_0_2 = obj_model.io.JsonReader().run(path, [AA])
        self.assertTrue(aa_0.is_equal(aa_0_2))

        path = os.path.join(self.dirname, 'out.abc')
        with self.assertRaisesRegexp(ValueError, 'Unsupported format'):
            obj_model.io.JsonWriter().run(path, aa_0)
        with self.assertRaisesRegexp(ValueError, 'Unsupported format'):
            obj_model.io.JsonReader().run(path, [AA])

        old_AA = AA

        class AA(core.Model):
            id = core.StringAttribute()
        path = os.path.join(self.dirname, 'out.yml')
        with self.assertRaisesRegexp(ValueError, 'Model names must be unique to decode objects'):
            obj_model.io.JsonWriter().run(path, aa_0, models=[AA, old_AA])
        with self.assertRaisesRegexp(ValueError, 'Model names must be unique to decode objects'):
            obj_model.io.JsonReader().run(path, models=[AA, old_AA])


class UtilsTestCase(unittest.TestCase):
    def test_get_writer(self):
        self.assertEqual(obj_model.io.get_writer('.csv'), obj_model.io.WorkbookWriter)
        self.assertEqual(obj_model.io.get_writer('.tsv'), obj_model.io.WorkbookWriter)
        self.assertEqual(obj_model.io.get_writer('.xlsx'), obj_model.io.WorkbookWriter)
        self.assertEqual(obj_model.io.get_writer('.json'), obj_model.io.JsonWriter)
        self.assertEqual(obj_model.io.get_writer('.yaml'), obj_model.io.JsonWriter)
        self.assertEqual(obj_model.io.get_writer('.yml'), obj_model.io.JsonWriter)

        with self.assertRaises(ValueError):
            obj_model.io.get_writer('.abc')

    def test_get_reader(self):
        self.assertEqual(obj_model.io.get_reader('.csv'), obj_model.io.WorkbookReader)
        self.assertEqual(obj_model.io.get_reader('.tsv'), obj_model.io.WorkbookReader)
        self.assertEqual(obj_model.io.get_reader('.xlsx'), obj_model.io.WorkbookReader)
        self.assertEqual(obj_model.io.get_reader('.json'), obj_model.io.JsonReader)
        self.assertEqual(obj_model.io.get_reader('.yaml'), obj_model.io.JsonReader)
        self.assertEqual(obj_model.io.get_reader('.yml'), obj_model.io.JsonReader)

        with self.assertRaises(ValueError):
            obj_model.io.get_reader('.abc')
