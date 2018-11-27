""" Test schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

import os
import sys
import unittest
from unittest import mock
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
        fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures')
        self.old_model_defs_path = os.path.join(fixtures_path, 'core_old.py')
        self.new_model_defs_path = os.path.join(fixtures_path, 'core_new.py')

        self.migrator = Migrator(self.old_model_defs_path, self.new_model_defs_path, None)
        self.migrator._get_all_model_defs()

        self.no_change_migrator = Migrator(self.old_model_defs_path, self.old_model_defs_path, None)

        self.tmp_dir = tempfile.mkdtemp()

        self.tmp_model_dir = self.__class__.tmp_model_dir
        shutil.copy(os.path.join(fixtures_path, 'example_old_model.xlsx'), self.tmp_model_dir)
        self.example_old_model = os.path.join(self.tmp_model_dir, 'example_old_model.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_valid_python_path(self):
        with self.assertRaisesRegex(ValueError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('test/foo/x.csv')
        with self.assertRaisesRegex(ValueError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('foo/.py')
        with self.assertRaisesRegex(ValueError, "module name '.*' in '.*' cannot contain a '.'"):
            Migrator._valid_python_path('foo/module.with.periods.py')

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

    def test_load_model_defs_file(self):
        module = self.migrator._load_model_defs_file(self.old_model_defs_path)
        self.assertEqual(module.__dict__['__name__'], 'core_old')
        self.assertEqual(module.__dict__['__file__'], self.old_model_defs_path)

    def test_get_model_defs(self):
        migrator = self.migrator
        module = migrator._load_model_defs_file(self.old_model_defs_path)
        models = Migrator._get_model_defs(module)
        self.assertEqual(set(models), {'DeletedModel', 'Reference', 'Subtest', 'Test', 'Property'})
        self.assertEqual(models['Test'].__name__, 'Test')

    def test_get_migrated_copy_attr_name(self):
        self.assertTrue(self.migrator._get_migrated_copy_attr_name().startswith(
            Migrator.MIGRATED_COPY_ATTR_PREFIX))

    def test_new_attributes(self):
        migrator = self.migrator
        model_name = 'Test'
        self.assertEqual(['new_attr'],
            migrator._new_attributes(migrator.old_model_defs[model_name],
                migrator.new_model_defs[model_name]))

    def test_deleted_attributes(self):
        migrator = self.migrator
        model_name = 'Test'
        self.assertEqual(['old_attr'],
            migrator._deleted_attributes(migrator.old_model_defs[model_name],
                migrator.new_model_defs[model_name]))

    def test_get_inconsistencies(self):
        migrator = self.migrator
        for model_name in migrator.old_model_defs:
            if model_name in migrator.new_model_defs:
                inconsistencies = Migrator._get_inconsistencies(migrator.old_model_defs[model_name],
                    migrator.new_model_defs[model_name])
                self.assertEqual([], inconsistencies)

        class RelatedObj(obj_model.Model):
            id = SlugAttribute()

        class TestOld(obj_model.Model):
            id = SlugAttribute()
            attr = StringAttribute()
            extra_attribute = extra_attributes.NumpyArrayAttribute()
            other_attr = StringAttribute()
            related = OneToOneAttribute(RelatedObj, related_name='test')

        class TestNew(obj_model.Model):
            id = SlugAttribute()
            attr = IntegerAttribute()
            new_attr = BooleanAttribute()
            extra_attribute = extra_attributes.NumpyArrayAttribute()
            other_attr = StringAttribute(unique=True)
            related = OneToOneAttribute(RelatedObj, related_name='not_test')

        inconsistencies = Migrator._get_inconsistencies(TestOld, TestNew)
        expected_inconsistencies = [
            "names differ: old model '.*' != new model '.*'",
            "types differ for '.*': old model '.*' != new model '.*'",
            "'.*' differs for '.*': old model '.*' != new model '.*'",
            "names differ for 'related.primary_class': old model '.*' != new model '.*'",
            "'.*' differs for '.*': old model '.*' != new model '.*'"]
        for inconsistency, expected_inconsistency in zip(inconsistencies, expected_inconsistencies):
            self.assertRegex(inconsistency, expected_inconsistency)

    def test_get_model_order(self):
        # todo: including ambiguous_sheet_names
        pass

    def test_prepare(self):
        migrator = self.migrator
        migrator.prepare()
        self.assertEqual(migrator.new_models, {'NewModel'})
        self.assertEqual(migrator.deleted_models, {'DeletedModel'})
        self.assertEqual(migrator.new_attributes, [('Test', 'new_attr')])
        self.assertEqual(migrator.deleted_attributes, [('Test', 'old_attr')])

    def test_migrate_model(self):

        class TestOld(obj_model.Model):
            id = SlugAttribute()
            old_attr = StringAttribute()
            attr1 = StringAttribute()
            extra_attribute = extra_attributes.NumpyArrayAttribute()

        class RelatedObj(obj_model.Model):
            id = SlugAttribute()

        default_new_attr = 'foo'
        class TestNew(obj_model.Model):
            id = SlugAttribute()
            new_attr = StringAttribute(default=default_new_attr)
            attr1 = StringAttribute()
            extra_attribute = extra_attributes.NumpyArrayAttribute()

        # force equivalent names for TestOld and TestNew since the are not loaded with importlib
        class_name = 'Test'
        for model in [TestOld, TestNew]:
            model.__name__ = class_name

        id = 'test_id'
        attr1 = None
        extra_attribute = numpy.array([1, 2])
        old_model = TestOld(id=id, old_attr='old_attr_val', attr1=attr1,
            extra_attribute=extra_attribute)

        mock_migrator = mock.Mock(spec=Migrator)
        mock_migrator.deleted_attributes = [(class_name, TestOld.Meta.attributes['old_attr'])]
        mock_migrator.new_attributes = [(class_name, TestNew.Meta.attributes['new_attr'])]
        mock_migrator._migrated_copy_attr_name = Migrator.MIGRATED_COPY_ATTR_PREFIX
        mock_migrator.migrate_model = Migrator.migrate_model
        new_model = mock_migrator.migrate_model(mock_migrator, old_model, TestOld, TestNew)

        self.assertTrue(isinstance(new_model, TestNew))
        self.assertFalse(hasattr(new_model, 'old_attr'))
        self.assertEqual(new_model.id, id)
        self.assertEqual(new_model.attr1, attr1)
        self.assertEqual(new_model.new_attr, default_new_attr)
        self.assertTrue(numpy.all(numpy.equal(new_model.extra_attribute, extra_attribute)))

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
            test=test,
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
            NewProperty(id=property_id, value=property_value, test=new_test))
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
            '''
            todo: why don't these produce symmetrical representations?
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
        print()
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
        # todo: custom migrate_suffix and ValueError

    def test_migrate(self):

        # test round-trip old -> new -> old
        old_2_new_migrator = self.migrator
        old_2_new_migrator.prepare()
        old_2_new_migrated_file = old_2_new_migrator.migrate(self.example_old_model)

        new_2_old_migrator = Migrator(self.new_model_defs_path, self.old_model_defs_path, None)
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
