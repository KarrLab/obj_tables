""" Test schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

import os
import sys
import re
import unittest
import getpass
from tempfile import mkdtemp
import shutil
import numpy
import copy
import warnings
from argparse import Namespace
import cProfile
import pstats
import yaml
from pprint import pprint, pformat

from obj_model.migrate import MigratorError, Migrator, MigrationController, RunMigration, MigrationDesc
import obj_model
from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation, migrate, math)
from wc_utils.workbook.io import read as read_workbook
from obj_model.expression import Expression


class MigrationFixtures(unittest.TestCase):
    """ Reused fixture set up and tear down
    """

    def setUp(self):
        self.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
        self.existing_defs_path = os.path.join(fixtures_path, 'core_existing.py')
        self.migrated_defs_path = os.path.join(fixtures_path, 'core_migrated.py')

        self.migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        self.migrator._load_defs_from_files()

        self.no_change_migrator = Migrator(self.existing_defs_path, self.existing_defs_path)
        self.no_change_migrator.prepare()

        self.tmp_dir = mkdtemp()

        # create tmp dir in 'fixtures/migrate/tmp' so it can be accessed from Docker container's host
        # copy test models to tmp dir
        self.tmp_model_dir = mkdtemp(dir=os.path.join(self.fixtures_path, 'tmp'))
        self.example_existing_model_copy = self.copy_fixtures_file_to_tmp('example_existing_model.xlsx')
        self.example_existing_rt_model_copy = self.copy_fixtures_file_to_tmp('example_existing_model_rt.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')

        dst = os.path.join(self.tmp_model_dir, 'tsv_example')
        self.tsv_dir = shutil.copytree(os.path.join(fixtures_path, 'tsv_example'), dst)
        self.tsv_test_model = 'test-*.tsv'
        self.example_existing_model_tsv = os.path.join(self.tsv_dir, self.tsv_test_model)
        # put each tsv in separate dir so globs don't match erroneously
        self.existing_2_migrated_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)
        self.round_trip_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)

        self.config_file = os.path.join(self.fixtures_path, 'config_example.yaml')

        ### create migrator with renaming that doesn't use models in files
        self.migrator_for_error_tests = migrator_for_error_tests = Migrator()

        ### these classes contain migration errors for validation tests ###
        ### existing models
        class RelatedObj(obj_model.Model):
            id = SlugAttribute()
        self.RelatedObj = RelatedObj

        class TestExisting(obj_model.Model):
            id = SlugAttribute()
            attr_a = StringAttribute()
            unmigrated_attr = StringAttribute()
            extra_attr_1 = math.NumpyArrayAttribute()
            other_attr = StringAttribute()
        self.TestExisting = TestExisting

        class TestExisting2(obj_model.Model):
            related = OneToOneAttribute(RelatedObj, related_name='test')

        class TestNotMigrated(obj_model.Model):
            id_2 = SlugAttribute()

        migrator_for_error_tests.existing_defs = {
            'RelatedObj': RelatedObj,
            'TestExisting': TestExisting,
            'TestExisting2': TestExisting2,
            'TestNotMigrated': TestNotMigrated}

        ### migrated models
        class NewRelatedObj(obj_model.Model):
            id = SlugAttribute()
        self.NewRelatedObj = NewRelatedObj

        class TestMigrated(obj_model.Model):
            id = SlugAttribute()
            attr_b = IntegerAttribute()
            migrated_attr = BooleanAttribute()
            extra_attr_2 = math.NumpyArrayAttribute()
            other_attr = StringAttribute(unique=True)

        class TestMigrated2(obj_model.Model):
            related = OneToOneAttribute(RelatedObj, related_name='not_test')

        migrator_for_error_tests.migrated_defs = {
            'NewRelatedObj': NewRelatedObj,
            'TestMigrated': TestMigrated,
            'TestMigrated2': TestMigrated2}

        ### renaming maps
        migrator_for_error_tests.renamed_models = [
            ('RelatedObj', 'NewRelatedObj'),
            ('TestExisting', 'TestMigrated'),
            ('TestExisting2', 'TestMigrated2')]
        migrator_for_error_tests.renamed_attributes = [
            (('TestExisting', 'attr_a'), ('TestMigrated', 'attr_b')),
            (('TestExisting', 'extra_attr_1'), ('TestMigrated', 'extra_attr_2'))]

        try:
            # ignore MigratorError exception which will be tested later
            migrator_for_error_tests.prepare()
        except MigratorError:
            pass

        self.migrator_for_error_tests_2 = migrator_for_error_tests_2 = Migrator()
        migrator_for_error_tests_2.existing_defs = migrator_for_error_tests.existing_defs
        migrator_for_error_tests_2.migrated_defs = migrator_for_error_tests.migrated_defs
        ### renaming maps
        migrator_for_error_tests_2.renamed_models = [
            ('TestExisting', 'TestMigrated'),
            ('TestExisting2', 'TestMigrated2')]
        migrator_for_error_tests_2.renamed_attributes = migrator_for_error_tests.renamed_attributes
        try:
            # ignore errors what are tested in TestMigration.test_get_inconsistencies
            migrator_for_error_tests_2.prepare()
        except MigratorError:
            pass

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
            np_array = math.NumpyArrayAttribute()
            related = OneToOneAttribute(GoodRelatedCls, related_name='test')
        self.GoodExisting = GoodExisting

        class GoodNotMigrated(obj_model.Model):
            id_2 = SlugAttribute()
        self.GoodNotMigrated = GoodNotMigrated

        # migrated models
        class GoodMigrated(obj_model.Model):
            id = SlugAttribute()
            attr_b = StringAttribute()
            np_array = math.NumpyArrayAttribute()
            related = OneToOneAttribute(RelatedObj, related_name='test_2')
        self.GoodMigrated = GoodMigrated

        self.good_migrator = good_migrator = Migrator()
        good_migrator.existing_defs = {
            'GoodRelatedCls': GoodRelatedCls,
            'GoodExisting': GoodExisting,
            'GoodNotMigrated': GoodNotMigrated}
        good_migrator.migrated_defs = {
            'GoodMigrated': GoodMigrated}
        good_migrator.renamed_models = [('GoodExisting', 'GoodMigrated')]
        good_migrator.renamed_attributes = [
            (('GoodExisting', 'attr_a'), ('GoodMigrated', 'attr_b'))]
        good_migrator._validate_renamed_models()
        good_migrator._validate_renamed_attrs()

        # set up round-trip schema fixtures
        self.existing_rt_model_defs_path = os.path.join(self.fixtures_path, 'core_existing_rt.py')
        self.migrated_rt_model_defs_path = os.path.join(self.fixtures_path, 'core_migrated_rt.py')
        # provide existing -> migrated renaming for the round-trip tests
        self.existing_2_migrated_renamed_models = [('Test', 'MigratedTest')]
        self.existing_2_migrated_renamed_attributes = [
            (('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr')),
            (('Property', 'value'), ('Property', 'migrated_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))]

        # set up wc_lang migration testing fixtures
        self.wc_lang_fixtures_path = os.path.join(self.fixtures_path, 'wc_lang')
        self.wc_lang_schema_existing = os.path.join(self.wc_lang_fixtures_path, 'core.py')
        self.wc_lang_schema_modified = os.path.join(self.wc_lang_fixtures_path, 'core_modified.py')
        self.wc_lang_model_copy = self.copy_fixtures_file_to_tmp('example-wc_lang-model.xlsx')
        self.wc_lang_small_model_copy = self.copy_fixtures_file_to_tmp('2_species_1_reaction.xlsx')
        self.wc_lang_no_model_attrs = self.copy_fixtures_file_to_tmp('wc_lang_model_w_no_model_attrs.xlsx')

        # set up expressions testing fixtures
        self.wc_lang_no_change_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_existing)
        self.wc_lang_changes_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_modified, renamed_models=[('Parameter', 'ParameterRenamed')])
        self.no_change_migrator_model = self.set_up_fun_expr_fixtures(
            self.wc_lang_no_change_migrator, 'Parameter', 'Parameter')
        self.changes_migrator_model = \
            self.set_up_fun_expr_fixtures(self.wc_lang_changes_migrator, 'Parameter', 'ParameterRenamed')

        # since MigrationDesc describes a sequence of migrations, embed renamings in lists
        self.migration_desc = MigrationDesc('name',
            existing_file=self.example_existing_rt_model_copy,
            model_defs_files=[self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path],
            seq_of_renamed_models=[self.existing_2_migrated_renamed_models],
            seq_of_renamed_attributes=[self.existing_2_migrated_renamed_attributes])

    def set_up_fun_expr_fixtures(self, migrator, existing_param_class, migrated_param_class):
        migrator.prepare()
        Model = migrator.existing_defs['Model']
        # define models in FunctionExpression.valid_used_models
        Function = migrator.existing_defs['Function']
        Observable = migrator.existing_defs['Observable']
        ParameterClass = migrator.existing_defs[existing_param_class]
        objects = {model: {} for model in [ParameterClass, Function, Observable]}
        # todo: test without Observable in objects; what traps the ParsedExpressionError?
        model = Model(id='test_model', version='0.0.0')
        param = model.parameters.create(id='param_1')
        objects[ParameterClass]['param_1'] = param
        fun_1 = Expression.make_obj(model, Function, 'fun_1', 'log10(10)', objects)
        objects[Function]['fun_1'] = fun_1
        Expression.make_obj(model, Function, 'fun_2', 'param_1 + 2* Function.fun_1()', objects)
        Expression.make_obj(model, Function, 'disambiguated_fun', 'Parameter.param_1 + 2* Function.fun_1()',
            objects)
        return model

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        shutil.rmtree(self.tmp_model_dir)

    @staticmethod
    def invert_renaming(renaming):
        # invert a list of renamed_models or renamed_attributes
        inverted_renaming = []
        for entry in renaming:
            existing, migrated = entry
            inverted_renaming.append((migrated, existing))
        return inverted_renaming

    def temp_pathname(testcase, name):
        # create a pathname for a file called name in new temp dir; will be discarded by tearDown()
        return os.path.join(mkdtemp(dir=testcase.tmp_model_dir), name)

    def copy_fixtures_file_to_tmp(self, name):
        # copy file 'name' to the tmp dir and return its pathname
        shutil.copy(os.path.join(self.fixtures_path, name), self.tmp_model_dir)
        return os.path.join(self.tmp_model_dir, name)

    def assert_equal_workbooks(self, existing_model_file, migrated_model_file, equal=True):
        # test whether a pair of model files are identical, or not identical if equal=False
        existing_workbook = read_workbook(existing_model_file)
        migrated_workbook = read_workbook(migrated_model_file)
        if equal:
            if not existing_workbook == migrated_workbook:
                # for debugging
                print("differences between existing_model_file '{}' and migrated_model_file '{}'".format(
                    existing_model_file, migrated_model_file))
                print(existing_workbook.difference(migrated_workbook))
            self.assertEqual(existing_workbook, migrated_workbook)
        else:
            self.assertNotEqual(existing_workbook, migrated_workbook)


class TestMigrator(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_valid_python_path(self):
        with self.assertRaisesRegex(MigratorError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('test/foo/x.csv')
        with self.assertRaisesRegex(MigratorError, "must be Python filename ending in '.py'"):
            Migrator._valid_python_path('foo/.py')
        with self.assertRaisesRegex(MigratorError, "module name '.*' in '.*' cannot contain a '.'"):
            Migrator._valid_python_path('foo/module.with.periods.py')

    def test_load_model_defs_file(self):
        module = self.migrator._load_model_defs_file(self.existing_defs_path)
        self.assertEqual(module.__dict__['__name__'], 'core_existing')
        self.assertEqual(module.__dict__['__file__'], self.existing_defs_path)

    def test_normalize_model_defs_file(self):
        _normalize_filename = Migrator._normalize_filename
        self.assertEqual(_normalize_filename('~'),
            _normalize_filename('~' + getpass.getuser()))
        self.assertEqual(_normalize_filename('~'),
            _normalize_filename('$HOME'))
        cur_dir = os.path.dirname(__file__)
        self.assertEqual(cur_dir,
            _normalize_filename(os.path.join(cur_dir, '..', os.path.basename(cur_dir))))

    def test_validate_transformations(self):
        migrator = Migrator()
        self.assertEqual(migrator._validate_transformations(), [])
        def a_callable(): pass
        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, a_callable))
        self.assertEqual(migrator._validate_transformations(), [])
        migrator = Migrator(transformations=3)
        self.assertIn("transformations should be a dict", migrator._validate_transformations()[0])
        migrator = Migrator(transformations={'FOO':3, Migrator.PREPARE_EXISTING_MODELS:2})
        self.assertRegex(migrator._validate_transformations()[0],
            "names of transformations .+ aren't a subset of the supported transformations")
        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, 3))
        errors = migrator._validate_transformations()
        for error in errors:
            self.assertRegex(error, "value for transformation '.+' is a\(n\) '.+', which isn't callable")

    def test_validate_renamed_models(self):
        migrator_for_error_tests = self.migrator_for_error_tests
        self.assertEqual(migrator_for_error_tests._validate_renamed_models(), [])
        self.assertEqual(migrator_for_error_tests.models_map,
            {'TestExisting': 'TestMigrated', 'RelatedObj': 'NewRelatedObj', 'TestExisting2': 'TestMigrated2'})

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
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'id'), ('NewRelatedObj', 'id'))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'no_attr'), (None, None))

    def test_get_model_defs(self):
        migrator = self.migrator
        module = migrator._load_model_defs_file(self.existing_defs_path)
        models = Migrator._get_model_defs(module)
        self.assertEqual(set(models), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(models['Test'].__name__, 'Test')

    def test_load_defs_from_files(self):
        migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        migrator._load_defs_from_files()
        self.assertEqual(set(migrator.existing_defs), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(set(migrator.migrated_defs), {'Test', 'NewModel', 'Property', 'Subtest', 'Reference'})
        migrator_no_files = Migrator()
        migrator_no_files._load_defs_from_files()
        self.assertEqual(migrator_no_files.existing_defs_path, None)
        self.assertEqual(migrator_no_files.migrated_defs_path, None)

    def test_get_migrated_copy_attr_name(self):
        self.assertTrue(self.migrator._get_migrated_copy_attr_name().startswith(
            Migrator.MIGRATED_COPY_ATTR_PREFIX))

    def test_get_inconsistencies(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        inconsistencies = migrator_for_error_tests._get_inconsistencies('NotExistingModel', 'NotMigratedModel')
        self.assertRegex(inconsistencies[0], "existing model .* not found in")
        self.assertRegex(inconsistencies[1], "migrated model .* corresponding to existing model .* not found in")

        class A(object): pass
        migrator_for_error_tests.existing_defs['A'] = A
        migrator_for_error_tests.models_map['A'] = 'X'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'NewRelatedObj')
        self.assertRegex(inconsistencies[0], "type of existing model '.*' doesn't equal type of migrated model '.*'")
        self.assertRegex(inconsistencies[1],
            "models map says '.*' migrates to '.*', but _get_inconsistencies parameters say '.*' migrates to '.*'")
        A.__name__ = 'foo'
        self.NewRelatedObj.__name__ = 'foo'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'NewRelatedObj')
        self.assertRegex(inconsistencies[1],
            "name of existing model class '.+' not equal to its name in the models map '.+'")
        self.assertRegex(inconsistencies[2],
            "name of migrated model class '.+' not equal to its name in the models map '.+'")
        # clean up
        del migrator_for_error_tests.existing_defs['A']
        del migrator_for_error_tests.models_map['A']
        A.__name__ = 'A'
        self.NewRelatedObj.__name__ = 'NewRelatedObj'

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting', 'TestMigrated')
        self.assertRegex(inconsistencies[0],
            "existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+")

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting2', 'TestMigrated2')
        self.assertRegex(inconsistencies[0],
            ".+\..+\..+ is '.+', which differs from the migrated value of .+\..+\..+, which is '.+'")
        self.assertRegex(inconsistencies[1],
            ".+\..+\..+ is '.+', which migrates to '.+', but it differs from .+\..+\..+, which is '.+'")

        inconsistencies = self.migrator_for_error_tests_2._get_inconsistencies('TestExisting2', 'TestMigrated2')
        self.assertRegex(inconsistencies[1],
            "existing model '.+' is not migrated, but is referenced by migrated attribute .+\..+")

    def test_get_model_order(self):
        migrator = self.migrator
        migrator.prepare()
        existing_model_order = migrator._get_existing_model_order(self.example_existing_model_copy)
        migrated_model_order = migrator._migrate_model_order(existing_model_order)
        expected_model_order = [migrator.migrated_defs[model]
            for model in ['Test', 'Property', 'Subtest', 'Reference', 'NewModel']]
        self.assertEqual(migrated_model_order, expected_model_order)
        class NoSuchModel(obj_model.Model): pass
        with self.assertRaisesRegex(MigratorError, "model 'NoSuchModel' not found in the model map"):
            migrator._migrate_model_order([NoSuchModel])

        # test ambiguous_sheet_names
        class FirstUnambiguousModel(obj_model.Model): pass

        class SecondUnambiguousModel(obj_model.Model): pass

        # models with ambiguous sheet names
        class TestModel(obj_model.Model): pass

        class TestModels(obj_model.Model): pass

        class TestModels3(obj_model.Model):
            class Meta(obj_model.Model.Meta):
                verbose_name = 'TestModel'

        class RenamedModel(obj_model.Model): pass

        class NewModel(obj_model.Model): pass

        migrator_2 = Migrator('', '')
        migrated_models = dict(
            TestModel=TestModel,
            TestModels=TestModels,
            TestModels3=TestModels3,
            FirstUnambiguousModel=FirstUnambiguousModel)
        migrator_2.existing_defs = copy.deepcopy(migrated_models)
        migrator_2.existing_defs['SecondUnambiguousModel'] = SecondUnambiguousModel

        migrator_2.migrated_defs = copy.deepcopy(migrated_models)
        migrator_2.migrated_defs['RenamedModel'] = RenamedModel
        migrator_2.migrated_defs['NewModel'] = NewModel
        migrator_2.models_map = dict(
            FirstUnambiguousModel='FirstUnambiguousModel',
            TestModel='TestModel',
            TestModels='TestModels',
            TestModels3='TestModels3',
            SecondUnambiguousModel='RenamedModel'
        )
        example_ambiguous_sheets = os.path.join(self.fixtures_path, 'example_ambiguous_sheets.xlsx')
        expected_order = ['FirstUnambiguousModel', 'RenamedModel', 'TestModel', 'TestModels', 'TestModels3', 'NewModel']
        with self.assertWarnsRegex(obj_model.io.IoWarning,
            "The following sheets cannot be unambiguously mapped to models:"):
            existing_model_order = migrator_2._get_existing_model_order(example_ambiguous_sheets)

        migrated_model_order = migrator_2._migrate_model_order(existing_model_order)
        self.assertEqual([m.__name__ for m in migrated_model_order], expected_order)

    def test_prepare(self):
        migrator = self.migrator
        migrator.prepare()
        self.assertEqual(migrator.deleted_models, {'DeletedModel'})

        migrator.renamed_models = [('Test', 'NoSuchModel')]
        with self.assertRaisesRegex(MigratorError, "'.*' in renamed models not a migrated model"):
            migrator.prepare()
        migrator.renamed_models = []

        migrator.renamed_attributes = [(('Test', 'name'), ('Test', 'no_such_name'))]
        with self.assertRaisesRegex(MigratorError, "'.*' in renamed attributes not a migrated model.attribute"):
            migrator.prepare()
        migrator.renamed_attributes = []

        # triggering inconsistencies in prepare() requires inconsistent model definitions on disk
        inconsistent_migrated_model_defs_path = os.path.join(self.fixtures_path, 'core_migrated_inconsistent.py')
        inconsistent_migrator = Migrator(self.existing_defs_path, inconsistent_migrated_model_defs_path)
        inconsistent_migrator._load_defs_from_files()
        with self.assertRaisesRegex(MigratorError,
            "existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+"):
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
        migrated_model = self.good_migrator._migrate_model(good_existing_1, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

        id = None
        good_existing_2 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            np_array=np_array_val
        )
        migrated_model = self.good_migrator._migrate_model(good_existing_2, self.GoodExisting, self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

    def test_migrate_expression(self):
        migrators = [self.wc_lang_no_change_migrator, self.wc_lang_changes_migrator]
        models = [self.no_change_migrator_model, self.changes_migrator_model]
        for migrator, model in zip(migrators, models):
            for fun in model.functions:
                if migrator == self.wc_lang_changes_migrator and fun.id == 'disambiguated_fun':
                    original_expr = fun.expression.expression
                    expected_expr = original_expr.replace('Parameter', 'ParameterRenamed')
                    wc_lang_expr = fun.expression._parsed_expression
                    self.assertEqual(migrator._migrate_expression(wc_lang_expr), expected_expr)
                else:
                    wc_lang_expr = fun.expression._parsed_expression
                    original_expr = fun.expression.expression
                    self.assertEqual(migrator._migrate_expression(wc_lang_expr), original_expr)

    def test_migrate_analyzed_expr(self):
        migrators = [self.wc_lang_no_change_migrator, self.wc_lang_changes_migrator]
        models = [self.no_change_migrator_model, self.changes_migrator_model]
        for migrator, model in zip(migrators, models):
            existing_non_expr_models = [model] + model.parameters + model.functions
            existing_function_expr_models = [fun.expression for fun in model.functions]
            all_existing_models = existing_non_expr_models + existing_function_expr_models
            migrated_models = migrator.migrate(all_existing_models)
            for existing_model, migrated_model in zip(all_existing_models, migrated_models):
                # objects that aren't expressions didn't need migrating
                if existing_model in existing_non_expr_models:
                    self.assertFalse(hasattr(migrated_model, Migrator.PARSED_EXPR))
                else:
                    self.assertTrue(hasattr(migrated_model, Migrator.PARSED_EXPR))
                    existing_expr = getattr(existing_model, Migrator.PARSED_EXPR)
                    migrated_expr = getattr(migrated_model, Migrator.PARSED_EXPR)
                    # for self.wc_lang_no_change_migrator, WcLangExpressions should be identical
                    # except for their objects
                    if migrator == self.wc_lang_no_change_migrator:
                        for attr in ['model_cls', 'attr', 'expression', '_py_tokens', 'errors']:
                            self.assertEqual(getattr(existing_expr, attr), getattr(migrated_expr, attr))
                    if migrator == self.changes_migrator_model:
                        for wc_token in migrated_expr._obj_model_tokens:
                            if hasattr(wc_token, 'model_type'):
                                self.assertTrue(getattr(wc_token, 'model_type') in
                                    self.changes_migrator_model.migrated_defs.values())
            duped_migrated_params = [migrated_models[1]]*2
            with self.assertRaisesRegex(MigratorError,
                "model type 'Parameter.*' has duplicated id: '.+'"):
                migrator._migrate_all_analyzed_exprs(zip(['ignored']*2, duped_migrated_params))

            if migrator == self.wc_lang_no_change_migrator:
                last_existing_fun_expr = all_existing_models[-1]
                last_existing_fun_expr._parsed_expression.expression = \
                    last_existing_fun_expr._parsed_expression.expression + ':'
                with self.assertRaisesRegex(MigratorError, "bad token"):
                    migrator._migrate_all_analyzed_exprs(list(zip(all_existing_models, migrated_models)))

    def test_deep_migrate_and_connect_models(self):
        # test both _deep_migrate and _connect_models because they need a similar test state
        migrator = self.migrator
        migrator.prepare()
        existing_defs = migrator.existing_defs

        # define model instances in the migrator.existing_defs schema
        test_id = 'test_id'
        ExistingTest = existing_defs['Test']
        test = ExistingTest(id=test_id, existing_attr='existing_attr')

        deleted_model = existing_defs['DeletedModel'](id='id')

        property_id = 'property_id'
        property_value = 7
        ExistingProperty = existing_defs['Property']
        property = ExistingProperty(id=property_id,
            test=None,
            value=property_value)

        ExistingReference = existing_defs['Reference']
        references = []
        num_references = 4
        for n in range(num_references):
            references.append(
                ExistingReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        ExistingSubtest = existing_defs['Subtest']
        subtests = []
        num_subtests = 3
        for n in range(num_subtests):
            subtests.append(
                ExistingSubtest(id="subtest_{}".format(n),
                    test=test,
                    references=references[n:n + 2]))

        existing_models = []
        existing_models.append(test)
        existing_models.append(deleted_model)
        existing_models.append(property)
        existing_models.extend(references)
        existing_models.extend(subtests)

        # define model instances in the migrated migrator.migrated_defs schema
        migrated_defs = migrator.migrated_defs
        expected_migrated_models = []

        MigratedTest = migrated_defs['Test']
        migrated_attr_default = MigratedTest.Meta.attributes['migrated_attr'].default
        expected_migrated_models.append(
            MigratedTest(id=test_id, migrated_attr=migrated_attr_default))

        MigratedProperty = migrated_defs['Property']
        expected_migrated_models.append(
            MigratedProperty(id=property_id, value=property_value))

        MigratedReference = migrated_defs['Reference']
        for n in range(num_references):
            expected_migrated_models.append(
                MigratedReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))

        MigratedSubtest = migrated_defs['Subtest']
        for n in range(num_subtests):
            expected_migrated_models.append(
                MigratedSubtest(id="subtest_{}".format(n)))

        all_models = migrator._deep_migrate(existing_models)

        migrated_models = [migrated_model for _, migrated_model in all_models]
        self.assertEqual(len(migrated_models), len(expected_migrated_models))
        for migrated_model, expected_migrated_model in zip(migrated_models, expected_migrated_models):
            self.assertTrue(migrated_model._is_equal_attributes(expected_migrated_model))

        expected_migrated_models_2 = []
        migrated_test = MigratedTest(id=test_id, migrated_attr=migrated_attr_default)
        expected_migrated_models_2.append(migrated_test)
        expected_migrated_models_2.append(
            MigratedProperty(id=property_id, value=property_value, test=None))
        migrated_references = []
        for n in range(num_references):
            migrated_references.append(
                MigratedReference(
                    id="reference_id_{}".format(n),
                    value="reference_value_{}".format(n)))
        expected_migrated_models_2.extend(migrated_references)
        migrated_subtests = []
        for n in range(num_subtests):
            migrated_subtests.append(
                MigratedSubtest(id="subtest_{}".format(n),
                    test=migrated_test,
                    references=migrated_references[n:n + 2]))
        expected_migrated_models_2.extend(migrated_subtests)

        migrator._connect_models(all_models)

        self.assertEqual(len(migrated_models), len(expected_migrated_models_2))
        for migrated_model, expected_migrated_model in zip(migrated_models, expected_migrated_models_2):
            # todo: why don't these produce symmetrical representations?
            '''
            print('\nmigrated_model:')
            migrated_model.pprint(max_depth=2)
            print('expected_migrated_model:')
            expected_migrated_model.pprint(max_depth=2)
            '''
            self.assertTrue(migrated_model.is_equal(expected_migrated_model))

    @staticmethod
    def read_model_file(model_file, models):
        reader = obj_model.io.Reader.get_reader(model_file)()
        return reader.run(model_file, models=models, ignore_sheet_order=True)

    def compare_model(self, model_cls, models, existing_file, migrated_file):
        # compare model_cls in existing_file against model_cls in migrated_file
        # existing_file and migrated_file must use the same models
        existing_wc_model = self.read_model_file(existing_file, models)
        migrated_wc_model = self.read_model_file(migrated_file, models)
        # this follows and compares all refs reachable from model_cls in existing_wc_model and migrated_wc_model
        if 1 < len(existing_wc_model[model_cls]) or 1 < len(migrated_wc_model[model_cls]):
            warnings.warn("might compare unequal models in lists of multiple models")
        existing_model = existing_wc_model[model_cls][0]
        migrated_model = migrated_wc_model[model_cls][0]
        self.assertTrue(existing_model.is_equal(migrated_model))

    def test_migrate_without_changes(self):
        no_change_migrator = self.no_change_migrator
        no_change_migrator.full_migrate(self.example_existing_model_copy, migrated_file=self.example_migrated_model)
        ExistingTest = no_change_migrator.existing_defs['Test']
        models = list(no_change_migrator.existing_defs.values())
        # this compares all Models in self.example_existing_model_copy and self.example_migrated_model because it follows the refs from Test
        self.compare_model(ExistingTest, models, self.example_existing_model_copy, self.example_migrated_model)
        self.assert_equal_workbooks(self.example_existing_model_copy, self.example_migrated_model)

        test_suffix = '_MIGRATED_FILE'
        migrated_filename = no_change_migrator.full_migrate(self.example_existing_model_copy, migrate_suffix=test_suffix)
        root, _ = os.path.splitext(self.example_existing_model_copy)
        self.assertEqual(migrated_filename, "{}{}.xlsx".format(root, test_suffix))

        with self.assertRaisesRegex(MigratorError, "migrated file '.*' already exists"):
            no_change_migrator.full_migrate(self.example_existing_model_copy, migrated_file=self.example_migrated_model)

    def test_transformations_in_full_migrate(self):
        # make PREPARE_EXISTING_MODELS & MODIFY_MIGRATED_MODELS transformations that invert each other
        def prepare_existing_models(migrator, existing_models):
            # increment the value of Property models
            for existing_model in existing_models:
                if isinstance(existing_model, migrator.existing_defs['Property']):
                    existing_model.value += +1

        def modify_migrated_models(migrator, migrated_models):
            # decrement the value of Property models
            for migrated_model in migrated_models:
                if isinstance(migrated_model, migrator.existing_defs['Property']):
                    migrated_model.value += -1

        transformations = {
            Migrator.PREPARE_EXISTING_MODELS: prepare_existing_models,
            Migrator.MODIFY_MIGRATED_MODELS: modify_migrated_models
        }
        migrator = Migrator(self.existing_defs_path, self.existing_defs_path, transformations=transformations)
        migrator.prepare()
        migrated_file = migrator.full_migrate(self.example_existing_model_copy)

        # test that inverted transformations make no changes
        self.assert_equal_workbooks(self.example_existing_model_copy, migrated_file)

    def test_full_migrate(self):

        # test round-trip existing -> migrated -> existing
        # use schemas with no deleted or migrated models so model files are identical
        # but include model and attr renaming so that existing != migrated

        # make existing -> migrated migrator
        existing_2_migrated_migrator = Migrator(self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path,
            renamed_models=self.existing_2_migrated_renamed_models, renamed_attributes=self.existing_2_migrated_renamed_attributes)
        existing_2_migrated_migrator.prepare()

        # make migrated -> existing migrator
        migrated_2_existing_migrator = Migrator(self.migrated_rt_model_defs_path, self.existing_rt_model_defs_path,
            renamed_models=self.invert_renaming(self.existing_2_migrated_renamed_models),
            renamed_attributes=self.invert_renaming(self.existing_2_migrated_renamed_attributes))
        migrated_2_existing_migrator.prepare()

        # round trip test of model in tsv file
        existing_2_migrated_migrator.full_migrate(self.example_existing_model_tsv, migrated_file=self.existing_2_migrated_migrated_tsv_file)
        migrated_2_existing_migrator.full_migrate(self.existing_2_migrated_migrated_tsv_file, migrated_file=self.round_trip_migrated_tsv_file)
        self.assert_equal_workbooks(self.example_existing_model_tsv, self.round_trip_migrated_tsv_file)

        # round trip test of model in xlsx file
        tmp_existing_2_migrated_xlsx_file = os.path.join(self.tmp_model_dir, 'existing_2_migrated_xlsx_file.xlsx')
        existing_2_migrated_migrator.full_migrate(self.example_existing_rt_model_copy, migrated_file=tmp_existing_2_migrated_xlsx_file)
        round_trip_migrated_xlsx_file = migrated_2_existing_migrator.full_migrate(tmp_existing_2_migrated_xlsx_file)
        self.assert_equal_workbooks(self.example_existing_rt_model_copy, round_trip_migrated_xlsx_file)

    def run_check_model_test(self, model, model_def, attr_name, default_value):
        # test _check_model() by setting an attribute to its default
        model_copy = model.copy()
        setattr(model_copy, attr_name, default_value)
        self.assertIn("'{}' lacks '{}'".format(model_def.__name__, attr_name),
            self.good_migrator._check_model(model_copy, model_def)[0])
        return model_copy

    def test_check_model_and_models(self):

        good_related = self.GoodRelatedCls(
            id='id_1',
            num=123)
        good_existing = self.GoodExisting(
            id='id_2',
            attr_a='hi mom',
            unmigrated_attr='x',
            np_array=numpy.array([1, 2]),
            related=good_related
        )
        all_models = [good_related, good_existing]
        self.assertEqual([], self.good_migrator._check_model(good_related, self.GoodRelatedCls))
        all_models.append(self.run_check_model_test(good_related, self.GoodRelatedCls, 'id', ''))
        all_models.append(self.run_check_model_test(good_related, self.GoodRelatedCls, 'num', None))

        self.assertEqual([], self.good_migrator._check_model(good_existing, self.GoodExisting))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'np_array', None))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'related', None))
        all_models.append(self.run_check_model_test(good_existing, self.GoodExisting, 'related', None))

        inconsistencies = self.good_migrator._check_models(all_models)
        self.assertEqual(len(inconsistencies), 4)
        self.assertEqual(len([problem for problem in inconsistencies if problem.startswith('1')]), 3)
        self.assertEqual(len([problem for problem in inconsistencies if problem.startswith('2')]), 1)

    def test_migrate_in_place(self):
        self.migrator.prepare()
        # migrate to example_migrated_model
        example_migrated_model = self.temp_pathname('example_migrated_model.xlsx')
        self.migrator.full_migrate(self.example_existing_model_copy, migrated_file=example_migrated_model)
        # migrate to self.example_existing_model_copy
        self.migrator.full_migrate(self.example_existing_model_copy, migrate_in_place=True)

        # validate
        self.assert_equal_workbooks(example_migrated_model, self.example_existing_model_copy)

    def test_exceptions(self):
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        migrator = Migrator(bad_module, self.migrated_defs_path)
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            migrator._load_defs_from_files()

    def test_generate_wc_lang_migrator(self):
        migrator = Migrator.generate_wc_lang_migrator()
        self.assertTrue(isinstance(migrator, Migrator))
        self.assertTrue(callable(migrator.transformations[Migrator.PREPARE_EXISTING_MODELS]))

        same_defs_migrator = Migrator.generate_wc_lang_migrator(existing_defs_file=self.wc_lang_schema_existing,
            migrated_defs_file=self.wc_lang_schema_existing)
        same_defs_migrator.prepare()
        # migrate self.wc_lang_no_model_attrs twice with the generate_wc_lang_migrator
        # the 1st migration adds model attributes, & the 2nd tests that they exist
        wc_lang_model_with_model_attrs = same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)
        self.assert_equal_workbooks(self.wc_lang_no_model_attrs, wc_lang_model_with_model_attrs, equal=False)
        migrated_file = same_defs_migrator.full_migrate(wc_lang_model_with_model_attrs)
        self.assert_equal_workbooks(wc_lang_model_with_model_attrs, migrated_file)

        bad_kwargs = dict(existing_defs_file='existing_defs.py', migrated_defs_file='migrated_defs.py',
            transformations='foo')
        with self.assertRaisesRegex(MigratorError, "'transformations' entry not allowed in kwargs:\\n.+"):
            Migrator.generate_wc_lang_migrator(**bad_kwargs)

        # raise exception for num models != 1 by creating PREPARE_EXISTING_MODELS that deletes the model
        current_prepare_existing_models_fun = same_defs_migrator.transformations[Migrator.PREPARE_EXISTING_MODELS]
        def delete_model_and_call_current(migrator, existing_models):
            model_cls = migrator.existing_defs['Model']
            existing_models = [model for model in existing_models if model.__class__ != model_cls]
            current_prepare_existing_models_fun(migrator, existing_models)
        same_defs_migrator.transformations[Migrator.PREPARE_EXISTING_MODELS] = delete_model_and_call_current
        with self.assertRaisesRegex(MigratorError,
            "existing models must have 1 Model instance, but \\d are present"):
            same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)

    def test_str(self):
        self.wc_lang_changes_migrator.prepare()
        str_value = str(self.wc_lang_changes_migrator)
        for attr in Migrator.SCALAR_ATTRS + Migrator.COLLECTIONS_ATTRS:
            self.assertIn(attr, str_value)
        for map_name in ['existing_defs', 'migrated_defs', 'models_map']:
            migrator_map = getattr(self.wc_lang_changes_migrator, map_name)
            for key in migrator_map:
                self.assertIn(key, str_value)

        empty_migrator = Migrator()
        str_value = str(empty_migrator)
        for attr in Migrator.SCALAR_ATTRS:
            self.assertNotRegex(str_value, '^' + attr + '$')


class TestMigrationDesc(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_get_migrations_config(self):
        migration_descs = MigrationDesc.get_migrations_config(self.config_file)
        self.assertIn('migration_with_renaming', migration_descs.keys())
        self.assertEqual(migration_descs['migration_with_renaming'].existing_file,
            'tests/fixtures/migrate/example_existing_model_rt.xlsx')

        temp_bad_config_example = os.path.join(self.tmp_dir, 'bad_config_example.yaml')
        with open(temp_bad_config_example, 'w') as file:
            file.write(u'migration:\n')
            file.write(u'    obj_defs: [core_migrated_rt.py, core_existing_rt.py]\n')
        with self.assertRaisesRegex(MigratorError, re.escape("disallowed attribute(s) found: {'obj_defs'}")):
            MigrationDesc.get_migrations_config(temp_bad_config_example)

        with self.assertRaisesRegex(MigratorError, "could not read migration config file: "):
            MigrationDesc.get_migrations_config(os.path.join(self.fixtures_path, 'no_file.yaml'))

    def test_validate(self):
        self.assertFalse(self.migration_desc.validate())
        md = copy.deepcopy(self.migration_desc)
        setattr(md, 'disallowed_attr', 'bad')
        self.assertEqual(md.validate(), ["disallowed attribute(s) found: {'disallowed_attr'}"])

        for attr in MigrationDesc._required_attrs:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, attr, None)
            self.assertEqual(md.validate(), ["missing required attribute '{}'".format(attr)])
            delattr(md, attr)
            self.assertEqual(md.validate(), ["missing required attribute '{}'".format(attr)])

        md = copy.deepcopy(self.migration_desc)
        md.model_defs_files = []
        self.assertEqual(md.validate(),
            ["model_defs_files must contain at least 2 model definitions, but it has only 0"])

        for renaming_list in MigrationDesc._renaming_lists:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, renaming_list, [[], []])
            error = md.validate()[0]
            self.assertRegex(error,
                "{} must have 1 .+ 1 migration.+ model_defs_files, but it has \d".format(renaming_list))

        for renaming_list in MigrationDesc._renaming_lists:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, renaming_list, None)
            self.assertFalse(md.validate())

        for renaming_list in MigrationDesc._renaming_lists:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, renaming_list, [None])
            self.assertEqual(md.validate(), [])

        bad_renamed_models_examples = [3, [('foo')], [('foo', 1)], [(1, 'bar')]]
        for bad_renamed_models in bad_renamed_models_examples:
            md = copy.deepcopy(self.migration_desc)
            md.seq_of_renamed_models = [bad_renamed_models]
            error = md.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_models must be None, or a list of lists of pairs of strs"))

        bad_renamed_attributes_examples = [
            [[('A', 'att1'), ('B', 'att2', 'extra')]],
            [[('A', 'att1'), ('B')]],
            [[(1, 'att1'), ('B', 'att2')]],
            [[('A', 2), ('B', 'att2')]],
            [3],
            ]
        for bad_renamed_attributes in bad_renamed_attributes_examples:
            md = copy.deepcopy(self.migration_desc)
            md.seq_of_renamed_attributes = [bad_renamed_attributes]
            error = md.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_attributes must be None, or a list of lists of pairs of pairs of strs"))

    def test_standardize(self):
        migration_descs = MigrationDesc.get_migrations_config(self.config_file)
        md = migration_descs['migration']
        for renaming in MigrationDesc._renaming_lists:
            self.assertEqual(len(getattr(md, renaming)), len(md.model_defs_files) - 1)
        seq_of_renamed_attributes = [
            [[['Test', 'existing_attr'], ['MigratedTest', 'migrated_attr']]],
            [[['Property', 'migrated_value'], ['Property', 'value']]]]
        migration_desc = MigrationDesc('name_2',
            model_defs_files=['x'],
            seq_of_renamed_attributes=seq_of_renamed_attributes)
        expected_renamed_attributes = [
            [(('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr'))],
            [(('Property', 'migrated_value'), ('Property', 'value'))]]
        migration_desc.standardize()
        self.assertEqual(migration_desc.seq_of_renamed_attributes, expected_renamed_attributes)

    def test_get_kwargs(self):
        kwargs = self.migration_desc.get_kwargs()
        self.assertEqual(kwargs['existing_file'], self.example_existing_rt_model_copy)
        self.assertEqual(kwargs['model_defs_files'], [self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path])
        self.assertEqual(kwargs['seq_of_renamed_models'], [self.existing_2_migrated_renamed_models])
        self.assertEqual(kwargs['seq_of_renamed_attributes'], [self.existing_2_migrated_renamed_attributes])
        self.assertEqual(kwargs['migrated_file'], None)
        self.migration_desc

    def test_str(self):
        migration_descs = MigrationDesc.get_migrations_config(self.config_file)
        name = 'migration_with_renaming'
        migration_desc = migration_descs[name]
        migration_desc_str = str(migration_desc)
        self.assertIn(name, migration_desc_str)
        self.assertIn(str(migration_desc.model_defs_files), migration_desc_str)


class TestMigrationController(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_migrate_over_schema_sequence(self):
        bad_migration_desc = copy.deepcopy(self.migration_desc)
        del bad_migration_desc.name
        with self.assertRaises(MigratorError):
            MigrationController.migrate_over_schema_sequence(bad_migration_desc)

        # round-trip test: existing -> migrated -> migrated -> existing
        model_defs_files = [self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path,
            self.migrated_rt_model_defs_path, self.existing_rt_model_defs_path]
        migrated_2_existing_renamed_models = self.invert_renaming(self.existing_2_migrated_renamed_models)
        migrated_2_existing_renamed_attributes = self.invert_renaming(self.existing_2_migrated_renamed_attributes)
        seq_of_renamed_models = [self.existing_2_migrated_renamed_models, [], migrated_2_existing_renamed_models]
        seq_of_renamed_attributes = [self.existing_2_migrated_renamed_attributes, [], migrated_2_existing_renamed_attributes]

        migrated_filename = self.temp_pathname('example_existing_model_rt_migrated.xlsx')
        migration_desc = MigrationDesc('name',
            existing_file=self.example_existing_rt_model_copy,
            model_defs_files=model_defs_files,
            seq_of_renamed_models=seq_of_renamed_models,
            seq_of_renamed_attributes=seq_of_renamed_attributes,
            migrated_file=migrated_filename)
        _, _, migrated_filename = MigrationController.migrate_over_schema_sequence(migration_desc)
        self.assert_equal_workbooks(self.example_existing_rt_model_copy, migrated_filename)

        with self.assertWarnsRegex(UserWarning,
            "\d+ instance\\(s\\) of existing model '\S+' lacks '\S+' non-default value"):
            MigrationController.migrate_over_schema_sequence(self.migration_desc)

    def put_tmp_migrated_file_in_migration_desc(self, migration_desc, name):
        migrated_filename = self.temp_pathname(name)
        migration_desc.migrated_file = migrated_filename
        return migrated_filename

    def test_migrate_from_desc(self):
        migration_descs = MigrationDesc.get_migrations_config(self.config_file)

        migration_desc = migration_descs['migration']
        tmp_migrated_filename = self.put_tmp_migrated_file_in_migration_desc(migration_desc, 'migration.xlsx')
        migrated_filename = MigrationController.migrate_from_desc(migration_desc)
        self.assertEqual(tmp_migrated_filename, migrated_filename)
        self.assert_equal_workbooks(migration_desc.existing_file, migrated_filename)

        migration_desc = migration_descs['migration_with_renaming']
        self.put_tmp_migrated_file_in_migration_desc(migration_desc, 'round_trip_migrated_xlsx_file.xlsx')
        round_trip_migrated_xlsx_file = MigrationController.migrate_from_desc(migration_desc)
        self.assert_equal_workbooks(migration_desc.existing_file, round_trip_migrated_xlsx_file)

    def test_migrate_from_config(self):
        # create a YAML config file with temp migrated filenames into avoid writing to tests/fixtures/migrate
        fd = open(self.config_file, 'r')
        migrations_config = yaml.load(fd)
        # add a migrated filename (migrated_file) to each migration description
        for migration_name, migration_desc in migrations_config.items():
            migration_desc['migrated_file'] = self.temp_pathname("migrated_file_4_{}.xlsx".format(migration_name))
        config_w_temp_migrated_filename = self.temp_pathname('config_w_temp_migrated_filename.yaml')
        stream = open(config_w_temp_migrated_filename, 'w')
        yaml.dump(migrations_config, stream)

        results = MigrationController.migrate_from_config(config_w_temp_migrated_filename)
        for migration_desc, migrated_file in results:
            self.assertEqual(migration_desc.migrated_file, migrated_file)
            self.assert_equal_workbooks(migration_desc.existing_file, migrated_file)

    def test_wc_lang_migration(self):

        # round-trip migrate through changed schema
        wc_lang_model_migrated = self.temp_pathname('wc_lang_small_model-migrated.xlsx')
        migration_desc = MigrationDesc('round-trip migrate existing wc_lang core -> modified core -> existing core',
            migrator=Migrator.generate_wc_lang_migrator,
            existing_file=self.wc_lang_small_model_copy,
            model_defs_files=[self.wc_lang_schema_existing, self.wc_lang_schema_modified, self.wc_lang_schema_existing],
            seq_of_renamed_models=[[('Parameter', 'ParameterRenamed')], [('ParameterRenamed', 'Parameter')]],
            migrated_file=wc_lang_model_migrated)
        MigrationController.migrate_over_schema_sequence(migration_desc)
        self.assert_equal_workbooks(self.wc_lang_small_model_copy, wc_lang_model_migrated)

        '''
        Process for round-trip migration of wc_lang model that lacks 'model' attributes
        1. to create model with 'model' attributes, migrate to tmp file w generate_wc_lang_migrator
        2. start with the tmp migrated file to test round-trip modification
        '''
        fully_instantiated_wc_lang_model = self.temp_pathname('fully_instantiated_wc_lang_model.xlsx')
        fully_instantiate_migration = MigrationDesc(
            "create fully instantiated model with 'model' attributes: migrate model from existing wc_lang core to itself",
            migrator=Migrator.generate_wc_lang_migrator,
            existing_file=self.wc_lang_model_copy,
            model_defs_files=[self.wc_lang_schema_existing, self.wc_lang_schema_existing],
            migrated_file=fully_instantiated_wc_lang_model)
        MigrationController.migrate_over_schema_sequence(fully_instantiate_migration)

        rt_through_changes_migration = MigrationDesc(
            "round trip migration though changes",
            existing_file=fully_instantiated_wc_lang_model,
            model_defs_files=[self.wc_lang_schema_existing, self.wc_lang_schema_modified,
                self.wc_lang_schema_existing],
            seq_of_renamed_models=[[('Parameter', 'ParameterRenamed')], [('ParameterRenamed', 'Parameter')]])
        _, _, rt_through_changes_wc_lang_model = \
            MigrationController.migrate_over_schema_sequence(rt_through_changes_migration)
        # validate round trip
        self.assert_equal_workbooks(fully_instantiated_wc_lang_model, rt_through_changes_wc_lang_model)

        # todo: remove
        '''
        # profile:
        out_file = self.temp_pathname('profile.out')
        print('out_file', out_file)
        locals = {'MigrationController':MigrationController,
            'rt_through_changes_migration':rt_through_changes_migration}
        cProfile.runctx('MigrationController.migrate_over_schema_sequence(rt_through_changes_migration)',
            {}, locals, filename=out_file)
        profile = pstats.Stats(out_file)
        print("Profile:")
        profile.strip_dirs().sort_stats('cumulative').print_stats(30)
        '''


class TestRunMigration(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_parse_args(self):
        existing_model_definitions = 'dir/file1.py'
        migrated_model_definitions = 'dir/file2.py'
        files = 'dir1/m1.xlsx dir1/m1.xlsx'
        cl = "{} {} {}".format(existing_model_definitions, migrated_model_definitions, files)
        args = RunMigration.parse_args(cli_args=cl.split())
        self.assertEqual(args.existing_model_definitions, existing_model_definitions)
        self.assertEqual(args.migrated_model_definitions, migrated_model_definitions)
        self.assertEqual(args.files, files.split())

    def test_main(self):
        args = Namespace(existing_model_definitions=self.existing_defs_path,
            migrated_model_definitions=self.migrated_defs_path, files=[self.example_existing_model_copy])
        migrated_files = RunMigration.main(args)
        root, ext = os.path.splitext(self.example_existing_model_copy)
        self.assertEqual(migrated_files[0], "{}{}{}".format(root, Migrator.MIGRATE_SUFFIX, ext))
