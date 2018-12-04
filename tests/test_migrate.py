""" Test schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

import os
import sys
import unittest
import getpass
import tempfile
import shutil
import numpy
import warnings
from argparse import Namespace

from obj_model.migrate import Migrator, RunMigration
import obj_model
from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation)
from obj_model import migrate, extra_attributes
from wc_utils.workbook.io import read as read_workbook


class TestMigration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # create tmp dir in 'fixtures/tmp' so it can be accessed from Docker container's host
        cls.tmp_model_dir = tempfile.mkdtemp(dir=os.path.join(os.path.dirname(__file__), 'fixtures', 'tmp'))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_model_dir)

    def setUp(self):
        self.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.old_model_defs_path = os.path.join(fixtures_path, 'core_old.py')
        self.new_model_defs_path = os.path.join(fixtures_path, 'core_new.py')

        self.migrator = Migrator(self.old_model_defs_path, self.new_model_defs_path, None)
        self.migrator.initialize()
        self.migrator._get_all_model_defs()

        self.no_change_migrator = Migrator(self.old_model_defs_path, self.old_model_defs_path, None)
        self.no_change_migrator.initialize()

        self.tmp_dir = tempfile.mkdtemp()

        self.tmp_model_dir = self.__class__.tmp_model_dir
        shutil.copy(os.path.join(fixtures_path, 'example_old_model.xlsx'), self.tmp_model_dir)
        self.example_old_model = os.path.join(self.tmp_model_dir, 'example_old_model.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')

        # create migrator with renaming that doesn't use models in files
        # these classes contain migration errors for validation tests
        # existing models
        class RelatedObj(obj_model.Model):
            id = SlugAttribute()

        class TestExisting(obj_model.Model):
            id = SlugAttribute()
            attr_a = StringAttribute()
            unmigrated_attr = StringAttribute()
            extra_attr_1 = extra_attributes.NumpyArrayAttribute()
            other_attr = StringAttribute()
            related = OneToOneAttribute(RelatedObj, related_name='test')
        self.TestExisting = TestExisting

        class TestNotMigrated(obj_model.Model):
            id_2 = SlugAttribute()

        # migrated models
        class NewRelatedObj(obj_model.Model):
            id = SlugAttribute()

        class TestMigrated(obj_model.Model):
            id = SlugAttribute()
            attr_b = IntegerAttribute()
            new_attr = BooleanAttribute()
            extra_attr_2 = extra_attributes.NumpyArrayAttribute()
            other_attr = StringAttribute(unique=True)
            related = OneToOneAttribute(NewRelatedObj, related_name='not_test')

        self.migrator_for_error_tests = migrator_for_error_tests = Migrator(
            'old_model_defs_file', 'new_model_defs_file', [])
        migrator_for_error_tests.old_model_defs = {
            'RelatedObj': RelatedObj,
            'TestExisting': TestExisting,
            'TestNotMigrated': TestNotMigrated}
        migrator_for_error_tests.new_model_defs = {
            'RelatedObj': RelatedObj,
            'TestMigrated': TestMigrated}
        migrator_for_error_tests.renamed_models = [('TestExisting', 'TestMigrated')]
        migrator_for_error_tests.renamed_attributes = [
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b')),
            (('TestExisting', 'extra_attr_1'), ('TestMigrated', 'extra_attr_2'))]

        # run _validate_renamed_models and _validate_renamed_attrs to create
        # migrator_for_error_tests.models_map and migrator_for_error_tests.renamed_attributes_map
        migrator_for_error_tests._validate_renamed_models()
        migrator_for_error_tests._validate_renamed_attrs()

        # create migrator with renaming that doesn't use models in files and doesn't have errors
        # existing models
        class GoodRelatedCls(obj_model.Model):
            id = SlugAttribute()
            num = IntegerAttribute()
        self.GoodRelatedCls = GoodRelatedCls

        class GoodExisting(obj_model.Model):
            id = SlugAttribute()
            attr_a = StringAttribute() # renamed to attr_b
            unmigrated_attr = StringAttribute()
            np_array = extra_attributes.NumpyArrayAttribute()
            related = OneToOneAttribute(GoodRelatedCls, related_name='test')
        self.GoodExisting = GoodExisting

        class GoodNotMigrated(obj_model.Model):
            id_2 = SlugAttribute()
        self.GoodNotMigrated = GoodNotMigrated

        # migrated models
        class GoodMigrated(obj_model.Model):
            id = SlugAttribute()
            attr_b = StringAttribute()
            np_array = extra_attributes.NumpyArrayAttribute()
            related = OneToOneAttribute(RelatedObj, related_name='test_2')
        self.GoodMigrated = GoodMigrated

        self.good_migrator = good_migrator = Migrator('old_model_defs_file', 'new_model_defs_file', [])
        good_migrator
        good_migrator.old_model_defs = {
            'GoodRelatedCls': GoodRelatedCls,
            'GoodExisting': GoodExisting,
            'GoodNotMigrated': GoodNotMigrated}
        good_migrator.new_model_defs = {
            'GoodMigrated': GoodMigrated}
        good_migrator.renamed_models = [('GoodExisting', 'GoodMigrated')]
        good_migrator.renamed_attributes = [
            (('GoodExisting', 'attr_a'), ('GoodMigrated', 'attr_b'))]
        good_migrator._validate_renamed_models()
        good_migrator._validate_renamed_attrs()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_valid_python_path(self):
        with self.assertRaisesRegex(ValueError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('test/foo/x.csv')
        with self.assertRaisesRegex(ValueError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('foo/.py')
        with self.assertRaisesRegex(ValueError, "module name '.*' in '.*' cannot contain a '.'"):
            Migrator._valid_python_path('foo/module.with.periods.py')

    def test_load_model_defs_file(self):
        module = self.migrator._load_model_defs_file(self.old_model_defs_path)
        self.assertEqual(module.__dict__['__name__'], 'core_old')
        self.assertEqual(module.__dict__['__file__'], self.old_model_defs_path)

    def test_normalize_model_defs_file(self):
        _normalize_filename = Migrator._normalize_filename
        self.assertEqual(_normalize_filename('~'),
            _normalize_filename('~' + getpass.getuser()))
        self.assertEqual(_normalize_filename('~'),
            _normalize_filename('$HOME'))
        cur_dir = os.path.dirname(__file__)
        self.assertEqual(cur_dir,
            _normalize_filename(os.path.join(cur_dir, '..', os.path.basename(cur_dir))))
        # todo: test sym links

    def test_validate_renamed_models(self):
        migrator_for_error_tests = self.migrator_for_error_tests
        self.assertEqual(migrator_for_error_tests._validate_renamed_models(), [])
        self.assertEqual(migrator_for_error_tests.models_map,
            {'TestExisting': 'TestMigrated', 'RelatedObj': 'RelatedObj'})

        # test errors
        migrator_for_error_tests.renamed_models = [('NotExisting', 'TestMigrated')]
        self.assertIn('in renamed models not an existing model',
            migrator_for_error_tests._validate_renamed_models()[0])
        self.assertEqual(migrator_for_error_tests.models_map, {})

        migrator_for_error_tests.renamed_models = [('TestExisting', 'NotMigrated')]
        self.assertIn('in renamed models not a migrated model',
            migrator_for_error_tests._validate_renamed_models()[0])

        migrator_for_error_tests.renamed_models = [
            ('TestExisting', 'TestMigrated'),
            ('TestExisting', 'TestMigrated')]
        errors = migrator_for_error_tests._validate_renamed_models()
        self.assertIn('duplicated existing models in renamed models:', errors[0])
        self.assertIn('duplicated migrated models in renamed models:', errors[1])

    def test_validate_renamed_attrs(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        self.assertEqual(migrator_for_error_tests._validate_renamed_attrs(), [])
        self.assertEqual(migrator_for_error_tests.renamed_attributes_map,
            dict(migrator_for_error_tests.renamed_attributes))

        # test errors
        for renamed_attributes in [
            [(('NotExisting', 'attr_a'), ('TestMigrated', 'attr_b'))],
            [(('TestExisting', 'no_such_attr'), ('TestMigrated', 'attr_b'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertIn('in renamed attributes not an existing model.attribute',
                migrator_for_error_tests._validate_renamed_attrs()[0])
        self.assertEqual(migrator_for_error_tests.renamed_attributes_map, {})

        for renamed_attributes in [
            [(('TestExisting', 'attr_a'), ('NotMigrated', 'attr_b'))],
            [(('TestExisting', 'attr_a'), ('TestMigrated', 'no_such_attr'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertIn('in renamed attributes not a migrated model.attribute',
                migrator_for_error_tests._validate_renamed_attrs()[0])

        for renamed_attributes in [
            [(('NotExisting', 'attr_a'), ('TestMigrated', 'attr_b'))],
            [(('TestExisting', 'attr_a'), ('NotMigrated', 'attr_b'))]]:
            migrator_for_error_tests.renamed_attributes = renamed_attributes
            self.assertRegex(migrator_for_error_tests._validate_renamed_attrs()[1],
                "renamed attribute '.*' not consistent with renamed models")

        migrator_for_error_tests.renamed_attributes = [
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b')),
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b'))]
        self.assertIn('duplicated existing attributes in renamed attributes:',
            migrator_for_error_tests._validate_renamed_attrs()[0])
        self.assertIn('duplicated migrated attributes in renamed attributes:',
            migrator_for_error_tests._validate_renamed_attrs()[1])

    def test_get_mapped_attribute(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('TestExisting', 'attr_a'),
            ('TestMigrated', 'attr_b'))

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute(
            self.TestExisting, self.TestExisting.Meta.attributes['id']), ('TestMigrated', 'id'))

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('TestExisting', 'no_attr'),
            (None, None))

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('NotExisting', 'id'), (None, None))

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'id'), ('RelatedObj', 'id'))

        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'no_attr'), (None, None))

    def test_get_model_defs(self):
        migrator = self.migrator
        module = migrator._load_model_defs_file(self.old_model_defs_path)
        models = Migrator._get_model_defs(module)
        self.assertEqual(set(models), {'DeletedModel', 'Reference', 'Subtest', 'Test', 'Property'})
        self.assertEqual(models['Test'].__name__, 'Test')

    def test_get_migrated_copy_attr_name(self):
        self.assertTrue(self.migrator._get_migrated_copy_attr_name().startswith(
            Migrator.MIGRATED_COPY_ATTR_PREFIX))

    def test_get_inconsistencies(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        # prep migrator_for_error_tests
        migrator_for_error_tests.old_model_defs_path = 'old_model_defs_path'
        migrator_for_error_tests.new_model_defs_path = 'new_model_defs_path'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('NotExistingModel', 'NotMigratedModel')
        self.assertRegex(inconsistencies[0], "old model .* not found in")
        self.assertRegex(inconsistencies[1], "new model .* corresponding to old model .* not found in")

        class A(object): pass
        migrator_for_error_tests.old_model_defs['A'] = A
        migrator_for_error_tests.models_map['A'] = 'X'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'RelatedObj')
        self.assertRegex(inconsistencies[0], "type of old model '.*' doesn't equal type of new model '.*'")
        self.assertRegex(inconsistencies[1],
            "models map says '.*' migrates to '.*', but _get_inconsistencies parameters say '.*' migrates to '.*'")
        # clean up
        del migrator_for_error_tests.old_model_defs['A']
        del migrator_for_error_tests.models_map['A']

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting', 'TestMigrated')
        self.assertRegex(inconsistencies[0],
            "migrated attribute type mismatch: type of .*, doesn't equal type of .*,")
        self.assertRegex(inconsistencies[1], "migrated attribute .* is .* but the existing .* is ")
        self.assertRegex(inconsistencies[2],
            "migrated attribute .* is .* but the model map says .* migrates to ")

    def test_get_model_order(self):
        # todo next: including ambiguous_sheet_names
        pass

    def test_prepare(self):
        migrator = self.migrator
        migrator.prepare()
        self.assertEqual(migrator.deleted_models, {'DeletedModel'})

        migrator.renamed_models = [('Test', 'NoSuchModel')]
        with self.assertRaisesRegex(ValueError, "'.*' in renamed models not a migrated model"):
            migrator.prepare()
        migrator.renamed_models = []

        migrator.renamed_attributes = [(('Test', 'name'), ('Test', 'no_such_name'))]
        with self.assertRaisesRegex(ValueError, "'.*' in renamed attributes not a migrated model.attribute"):
            migrator.prepare()
        migrator.renamed_attributes = []

        # triggering inconsistencies in prepare() requires inconsistent model definitions on disk
        inconsistent_new_model_defs_path = os.path.join(self.fixtures_path, 'core_new_inconsistent.py')
        inconsistent_migrator = Migrator(self.old_model_defs_path, inconsistent_new_model_defs_path, None)
        inconsistent_migrator.initialize()
        with self.assertRaisesRegex(ValueError,
            "migrated attribute type mismatch: type of .*, doesn't equal type of .*, .*"):
            inconsistent_migrator.prepare()

    def test_migrate_model(self):
        good_migrator = self.good_migrator
        good_migrator._migrated_copy_attr_name = good_migrator._get_migrated_copy_attr_name()

        # create good model(s) and migrate them
        grc_1 = self.GoodRelatedCls(id='grc_1', num=3)
        id = 'id_1'
        attr_a_b = 'string attr'
        np_array_val = numpy.array([1, 2])
        good_existing_1 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            unmigrated_attr='hi',
            np_array=np_array_val,
            related=grc_1
        )
        migrated_model = self.good_migrator.migrate_model(good_existing_1, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

        id = None
        good_existing_2 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            np_array=np_array_val
        )
        migrated_model = self.good_migrator.migrate_model(good_existing_2, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

    def test_deep_migrate_and_connect_models(self):
        # test both deep_migrate and connect_models because they need a similar test state
        migrator = self.migrator
        migrator.prepare()
        old_model_defs = migrator.old_model_defs

        # define models in the migrator.old_model_defs schema
        test_id = 'test_id'
        OldTest = old_model_defs['Test']
        test = OldTest(id=test_id, old_attr='old_attr')

        deleted_model = old_model_defs['DeletedModel'](id='id')

        property_id = 'property_id'
        property_value = 7
        OldProperty = old_model_defs['Property']
        property = OldProperty(id=property_id,
            test=None,
            value=property_value)

        OldReference = old_model_defs['Reference']
        references = []
        num_references = 4
        for n in range(num_references):
            references.append(
                OldReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        OldSubtest = old_model_defs['Subtest']
        subtests = []
        num_subtests = 3
        for n in range(num_subtests):
            subtests.append(
                OldSubtest(id="subtest_{}".format(n),
                    test=test,
                    references=references[n:n + 2]))

        old_models = []
        old_models.append(test)
        old_models.append(deleted_model)
        old_models.append(property)
        old_models.extend(references)
        old_models.extend(subtests)

        new_model_defs = migrator.new_model_defs
        expected_new_models = []

        NewTest = new_model_defs['Test']
        new_attr_default = NewTest.Meta.attributes['new_attr'].default
        expected_new_models.append(
            NewTest(id=test_id, new_attr=new_attr_default))

        NewProperty = new_model_defs['Property']
        expected_new_models.append(
            NewProperty(id=property_id, value=property_value))

        NewReference = new_model_defs['Reference']
        for n in range(num_references):
            expected_new_models.append(
                NewReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        NewSubtest = new_model_defs['Subtest']
        for n in range(num_subtests):
            expected_new_models.append(
                NewSubtest(id="subtest_{}".format(n)))

        all_models = migrator.deep_migrate(old_models)

        new_models = [new_model for _, new_model in all_models]
        self.assertEqual(len(new_models), len(expected_new_models))
        for new_model, expected_new_model in zip(new_models, expected_new_models):
            self.assertTrue(new_model._is_equal_attributes(expected_new_model))

        expected_new_models_2 = []
        new_test = NewTest(id=test_id, new_attr=new_attr_default)
        expected_new_models_2.append(new_test)
        expected_new_models_2.append(
            NewProperty(id=property_id, value=property_value, test=None))
        new_references = []
        for n in range(num_references):
            new_references.append(
                NewReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))
        expected_new_models_2.extend(new_references)
        new_subtests = []
        for n in range(num_subtests):
            new_subtests.append(
                NewSubtest(id="subtest_{}".format(n),
                    test=new_test,
                    references=new_references[n:n + 2]))
        expected_new_models_2.extend(new_subtests)

        migrator.connect_models(all_models)

        self.assertEqual(len(new_models), len(expected_new_models_2))
        for new_model, expected_new_model in zip(new_models, expected_new_models_2):
            # todo: why don't these produce symmetrical representations?
            '''
            print('\nnew_model:')
            new_model.pprint(max_depth=2)
            print('expected_new_model:')
            expected_new_model.pprint(max_depth=2)
            '''
            self.assertTrue(new_model.is_equal(expected_new_model))

    @staticmethod
    def read_model_file(model_file, models):
        _, ext = os.path.splitext(model_file)
        reader = obj_model.io.get_reader(ext)()
        return reader.run(model_file, models=models, ignore_sheet_order=True)

    def compare_model(self, model_cls, models, old_file, migrated_file):
        # compare model_cls in old_file against model_cls in migrated_file
        # old_file and migrated_file must use the same models
        old_wc_model = self.read_model_file(old_file, models)
        migrated_wc_model = self.read_model_file(migrated_file, models)
        # this follows and compares all refs reachable from model_cls in old_wc_model and migrated_wc_model
        if 1 < len(old_wc_model[model_cls]) or 1 < len(migrated_wc_model[model_cls]):
            warnings.warn("might compare unequal models in lists of multiple models")
        old_model = old_wc_model[model_cls][0]
        migrated_model = migrated_wc_model[model_cls][0]
        self.assertTrue(old_model.is_equal(migrated_model))

    def test_migrate_without_changes(self):
        no_change_migrator = self.no_change_migrator
        no_change_migrator.prepare()
        no_change_migrator.migrate(self.example_old_model, migrated_file=self.example_migrated_model)
        OldTest = no_change_migrator.old_model_defs['Test']
        models = list(no_change_migrator.old_model_defs.values())
        # this compares all Models in self.example_old_model and self.example_migrated_model because it follows the refs from Test
        self.compare_model(OldTest, models, self.example_old_model, self.example_migrated_model)

        source = read_workbook(self.example_old_model)
        migrated = read_workbook(self.example_migrated_model)
        self.assertEqual(source, migrated)
        # todo next: custom migrate_suffix and ValueError

    def test_migrate(self):

        # test round-trip old -> new -> old
        old_2_new_migrator = self.migrator
        old_2_new_migrator.prepare()
        old_2_new_migrated_file = old_2_new_migrator.migrate(self.example_old_model)

        new_2_old_migrator = Migrator(self.new_model_defs_path, self.old_model_defs_path, None)
        new_2_old_migrator.initialize()
        new_2_old_migrator.prepare()
        new_2_old_migrated_file = new_2_old_migrator.migrate(old_2_new_migrated_file)

        OldTest = old_2_new_migrator.old_model_defs['Test']
        models = list(old_2_new_migrator.old_model_defs.values())
        self.compare_model(OldTest, models, self.example_old_model, new_2_old_migrated_file)

    def test_exceptions(self):
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        migrator = Migrator(bad_module, self.new_model_defs_path, None)
        migrator.initialize()
        with self.assertRaisesRegex(ValueError, "cannot be imported and exec'ed"):
            migrator._load_model_defs_file(migrator.old_model_defs_path)


class TestRunMigration(unittest.TestCase):

    def setUp(self):
        fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.old_model_defs_path = os.path.join(fixtures_path, 'core_old.py')
        self.new_model_defs_path = os.path.join(fixtures_path, 'core_new.py')

        self.tmp_model_dir = tempfile.mkdtemp()
        shutil.copy(os.path.join(fixtures_path, 'example_old_model.xlsx'), self.tmp_model_dir)
        self.example_old_model = os.path.join(self.tmp_model_dir, 'example_old_model.xlsx')

    def tearDown(self):
        shutil.rmtree(self.tmp_model_dir)

    def test_parse_args(self):
        existing_model_definitions = 'dir/file1.py'
        new_model_definitions = 'dir/file2.py'
        files = 'dir1/m1.xlsx dir1/m1.xlsx'
        cl = "{} {} {}".format(existing_model_definitions, new_model_definitions, files)
        args = RunMigration.parse_args(cli_args=cl.split())
        self.assertEqual(args.existing_model_definitions, existing_model_definitions)
        self.assertEqual(args.new_model_definitions, new_model_definitions)
        self.assertEqual(args.files, files.split())

    def run_migration(self, old_models, new_models, biomodel_file):
        args = Namespace(existing_model_definitions=old_models, new_model_definitions=new_models,
            files=[biomodel_file])
        return RunMigration.main(args)

    def test_run_migration(self):
        migrated_example_model = self.run_migration(self.old_model_defs_path, self.new_model_defs_path,
            self.example_old_model)
        # todo: make unittest
