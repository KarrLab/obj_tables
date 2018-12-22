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
import filecmp
from argparse import Namespace
import cProfile
import pstats

from obj_model.migrate import MigratorError, Migrator, MigrationController, RunMigration, MigrationDesc
import obj_model
from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    TabularOrientation, migrate, 
    math)
from wc_utils.workbook.io import read as read_workbook
from obj_model.expression import Expression


class MigrationFixtures(unittest.TestCase):
    """ Reused fixture set up and tear down
    """

    def setUp(self):
        self.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
        self.old_model_defs_path = os.path.join(fixtures_path, 'core_old.py')
        self.new_model_defs_path = os.path.join(fixtures_path, 'core_new.py')

        self.migrator = Migrator(self.old_model_defs_path, self.new_model_defs_path)
        self.migrator.initialize()
        self.migrator._get_all_model_defs()

        self.no_change_migrator = Migrator(self.old_model_defs_path, self.old_model_defs_path)
        self.no_change_migrator.initialize()

        self.tmp_dir = mkdtemp()

        # create tmp dir in 'fixtures/migrate/tmp' so it can be accessed from Docker container's host
        # copy test models to tmp dir
        self.tmp_model_dir = mkdtemp(dir=os.path.join(self.fixtures_path, 'tmp'))
        shutil.copy(os.path.join(fixtures_path, 'example_old_model.xlsx'), self.tmp_model_dir)
        self.example_old_model_copy = os.path.join(self.tmp_model_dir, 'example_old_model.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')
        shutil.copy(os.path.join(self.fixtures_path, 'example_old_model_rt.xlsx'), self.tmp_model_dir)
        self.example_old_rt_model_copy = os.path.join(self.tmp_model_dir, 'example_old_model_rt.xlsx')

        dst = os.path.join(self.tmp_model_dir, 'tsv_example')
        self.tsv_dir = shutil.copytree(os.path.join(fixtures_path, 'tsv_example'), dst)
        self.tsv_test_model = 'test-*.tsv'
        self.example_old_model_tsv = os.path.join(self.tsv_dir, self.tsv_test_model)
        # put each tsv in separate dir so globs don't match erroneously
        self.old_2_new_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)
        self.round_trip_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)

        self.config_file = os.path.join(self.fixtures_path, 'config_example.yaml')

        ### create migrator with renaming that doesn't use models in files
        ### these classes contain migration errors for validation tests
        # existing models
        class RelatedObj(obj_model.Model):
            id = SlugAttribute()

        class TestExisting(obj_model.Model):
            id = SlugAttribute()
            attr_a = StringAttribute()
            unmigrated_attr = StringAttribute()
            extra_attr_1 = math.NumpyArrayAttribute()
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
            extra_attr_2 = math.NumpyArrayAttribute()
            other_attr = StringAttribute(unique=True)
            related = OneToOneAttribute(NewRelatedObj, related_name='not_test')

        self.migrator_for_error_tests = migrator_for_error_tests = Migrator(
            'old_model_defs_file', 'new_model_defs_file')
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
        # find deleted models
        used_models = set([existing_model for existing_model in migrator_for_error_tests.models_map])
        migrator_for_error_tests.deleted_models = \
            set(migrator_for_error_tests.old_model_defs).difference(used_models)

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

        self.good_migrator = good_migrator = Migrator('old_model_defs_file', 'new_model_defs_file')
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

        # set up round-trip schema fixtures
        self.old_rt_model_defs_path = os.path.join(self.fixtures_path, 'core_old_rt.py')
        self.new_rt_model_defs_path = os.path.join(self.fixtures_path, 'core_new_rt.py')

        # set up wc_lang migration testing fixtures
        self.wc_lang_fixtures_path = os.path.join(self.fixtures_path, 'wc_lang')
        self.wc_lang_schema_existing = os.path.join(self.wc_lang_fixtures_path, 'core.py')
        self.wc_lang_schema_modified = os.path.join(self.wc_lang_fixtures_path, 'core_modified.py')
        self.wc_lang_model_copy = self.copy_fixtures_file_to_tmp('example-wc_lang-model.xlsx')

        # set up expressions testing fixtures
        self.wc_lang_no_change_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_existing)
        self.wc_lang_changes_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_modified, renamed_models=[('Parameter', 'ParameterRenamed')])
        self.no_change_migrator_model = self.set_up_fun_expr_fixtures(
            self.wc_lang_no_change_migrator, 'Parameter', 'Parameter')
        self.changes_migrator_model = \
            self.set_up_fun_expr_fixtures(self.wc_lang_changes_migrator, 'Parameter', 'ParameterRenamed')

    def set_up_fun_expr_fixtures(self, migrator, existing_param_class, migrated_param_class):
        migrator.initialize()
        migrator.prepare()
        Model = migrator.old_model_defs['Model']
        # define models in FunctionExpression.valid_used_models
        Function = migrator.old_model_defs['Function']
        Observable = migrator.old_model_defs['Observable']
        ParameterClass = migrator.old_model_defs[existing_param_class]
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
    def get_roundtrip_renaming():
        # provide old -> new renaming for the round-trip tests
        old_2_new_renamed_models = [('Test', 'MigratedTest')]
        old_2_new_renamed_attributes = [
            (('Test', 'old_attr'), ('MigratedTest', 'new_attr')),
            (('Property', 'value'), ('Property', 'new_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))]
        return (old_2_new_renamed_models, old_2_new_renamed_attributes)

    @staticmethod
    def invert_renaming(renaming):
        # invert a list of renamed_models or renamed_attributes
        inverted_renaming = []
        for entry in renaming:
            existing, migrated = entry
            inverted_renaming.append((migrated, existing))
        return inverted_renaming

    def get_temp_pathname(testcase, name):
        # create a pathname for a file called name in new temp dir; will be discarded by tearDown()
        return os.path.join(mkdtemp(dir=testcase.tmp_model_dir), name)

    def copy_fixtures_file_to_tmp(self, name):
        # copy file 'name' to the tmp dir and return its pathname
        shutil.copy(os.path.join(self.fixtures_path, name), self.tmp_model_dir)
        return os.path.join(self.tmp_model_dir, name)


class TestMigration(MigrationFixtures):

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
        migrator = self.migrator
        migrator.prepare()
        existing_model_order = migrator._get_existing_model_order(self.example_old_model_copy)
        migrated_model_order = migrator._migrate_model_order(existing_model_order)
        expected_model_order = [migrator.new_model_defs[model]
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
        migrator_2.old_model_defs = copy.deepcopy(migrated_models)
        migrator_2.old_model_defs['SecondUnambiguousModel'] = SecondUnambiguousModel

        migrator_2.new_model_defs = copy.deepcopy(migrated_models)
        migrator_2.new_model_defs['RenamedModel'] = RenamedModel
        migrator_2.new_model_defs['NewModel'] = NewModel
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

    # @unittest.skip('skipping until _get_inconsistencies() is refactored')
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
        '''
        inconsistent_new_model_defs_path = os.path.join(self.fixtures_path, 'core_new_inconsistent.py')
        inconsistent_migrator = Migrator(self.old_model_defs_path, inconsistent_new_model_defs_path)
        inconsistent_migrator.initialize()
        with self.assertRaisesRegex(MigratorError,
            "migrated attribute type mismatch: type of .*, doesn't equal type of .*, .*"):
            inconsistent_migrator.prepare()
        '''

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
                                    self.changes_migrator_model.new_model_defs.values())
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
        old_model_defs = migrator.old_model_defs

        # define model instances in the migrator.old_model_defs schema
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

        # define model instances in the migrated migrator.new_model_defs schema
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

        all_models = migrator._deep_migrate(old_models)

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

        migrator._connect_models(all_models)

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
        no_change_migrator.full_migrate(self.example_old_model_copy, migrated_file=self.example_migrated_model)
        OldTest = no_change_migrator.old_model_defs['Test']
        models = list(no_change_migrator.old_model_defs.values())
        # this compares all Models in self.example_old_model_copy and self.example_migrated_model because it follows the refs from Test
        self.compare_model(OldTest, models, self.example_old_model_copy, self.example_migrated_model)

        source = read_workbook(self.example_old_model_copy)
        migrated = read_workbook(self.example_migrated_model)
        self.assertEqual(source, migrated)

        test_suffix = '_MIGRATED_FILE'
        migrated_filename = no_change_migrator.full_migrate(self.example_old_model_copy, migrate_suffix=test_suffix)
        root, _ = os.path.splitext(self.example_old_model_copy)
        self.assertEqual(migrated_filename, "{}{}.xlsx".format(root, test_suffix))

        with self.assertRaisesRegex(MigratorError, "migrated file '.*' already exists"):
            no_change_migrator.full_migrate(self.example_old_model_copy, migrated_file=self.example_migrated_model)

    def test_full_migrate(self):

        # test round-trip old -> new -> old
        # use schemas with no deleted or new models so model files are identical
        # but include model and attr renamng so that old != new

        # make old -> new migrator
        old_2_new_renamed_models, old_2_new_renamed_attributes = MigrationFixtures.get_roundtrip_renaming()
        old_2_new_migrator = Migrator(self.old_rt_model_defs_path, self.new_rt_model_defs_path,
            renamed_models=old_2_new_renamed_models, renamed_attributes=old_2_new_renamed_attributes)
        old_2_new_migrator.initialize().prepare()

        # make new -> old migrator
        new_2_old_migrator = Migrator(self.new_rt_model_defs_path, self.old_rt_model_defs_path,
            renamed_models=self.invert_renaming(old_2_new_renamed_models),
            renamed_attributes=self.invert_renaming(old_2_new_renamed_attributes))
        new_2_old_migrator.initialize().prepare()

        # round trip test of model in tsv file
        old_2_new_migrator.full_migrate(self.example_old_model_tsv, migrated_file=self.old_2_new_migrated_tsv_file)
        new_2_old_migrator.full_migrate(self.old_2_new_migrated_tsv_file, migrated_file=self.round_trip_migrated_tsv_file)

        existing = read_workbook(self.example_old_model_tsv)
        round_trip_migrated = read_workbook(self.round_trip_migrated_tsv_file)
        self.assertEqual(existing, round_trip_migrated)

        # round trip test of model in xlsx file
        tmp_old_2_new_xlsx_file = os.path.join(self.tmp_model_dir, 'old_2_new_xlsx_file.xlsx')
        old_2_new_migrator.full_migrate(self.example_old_rt_model_copy, migrated_file=tmp_old_2_new_xlsx_file)
        round_trip_migrated_xlsx_file = new_2_old_migrator.full_migrate(tmp_old_2_new_xlsx_file)

        existing = read_workbook(self.example_old_rt_model_copy)
        round_trip_migrated = read_workbook(round_trip_migrated_xlsx_file)
        self.assertEqual(existing, round_trip_migrated)

    def test_migrate_in_place(self):
        self.migrator.prepare()
        # migrate to example_migrated_model
        example_migrated_model = os.path.join(mkdtemp(dir=self.tmp_model_dir), 'example_migrated_model.xlsx')
        self.migrator.full_migrate(self.example_old_model_copy, migrated_file=example_migrated_model)
        # migrate to self.example_old_model_copy
        self.migrator.full_migrate(self.example_old_model_copy, migrate_in_place=True)

        # validate
        migrated = read_workbook(example_migrated_model)
        migrated_in_place = read_workbook(self.example_old_model_copy)
        self.assertEqual(migrated, migrated_in_place)

    def test_exceptions(self):
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        migrator = Migrator(bad_module, self.new_model_defs_path)
        migrator.initialize()
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            migrator._load_model_defs_file(migrator.old_model_defs_path)

    def test_str(self):
        self.assertIn('new_model_defs:', str(self.good_migrator))
        self.assertIn(str(self.good_migrator.new_model_defs), str(self.good_migrator))


class TestMigrationController(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_migrate_over_schema_sequence(self):
        # round-trip test: existing -> migrated -> migrated -> existing
        model_defs_files = [self.old_rt_model_defs_path, self.new_rt_model_defs_path,
            self.new_rt_model_defs_path, self.old_rt_model_defs_path]
        old_2_new_renamed_models, old_2_new_renamed_attributes = MigrationFixtures.get_roundtrip_renaming()
        new_2_old_renamed_models = self.invert_renaming(old_2_new_renamed_models)
        new_2_old_renamed_attributes = self.invert_renaming(old_2_new_renamed_attributes)
        renamed_models = [old_2_new_renamed_models, [], new_2_old_renamed_models]
        renamed_attributes = [old_2_new_renamed_attributes, [], new_2_old_renamed_attributes]

        migrated_filename = self.get_temp_pathname('example_old_model_rt_migrated.xlsx')
        migration_desc = MigrationDesc('name',
            existing_file=self.example_old_rt_model_copy,
            model_defs_files=model_defs_files,
            renamed_models=renamed_models,
            renamed_attributes=renamed_attributes,
            migrated_file=migrated_filename)
        migrated_filename = MigrationController.migrate_over_schema_sequence(migration_desc)

        # validate
        existing = read_workbook(self.example_old_rt_model_copy)
        round_trip_migrated = read_workbook(migrated_filename)
        self.assertEqual(existing, round_trip_migrated)

    def test_get_migrations_config(self):

        migration_descs = MigrationController.get_migrations_config(self.config_file)
        self.assertIn('migration_with_renaming', migration_descs.keys())
        self.assertEqual(migration_descs['migration_with_renaming'].existing_file,
            'tests/fixtures/migrate/example_old_model_rt.xlsx')

        temp_bad_config_example = os.path.join(self.tmp_dir, 'bad_config_example.yaml')
        with open(temp_bad_config_example, 'w') as file:
            file.write(u'migration:\n')
            file.write(u'    obj_defs: [core_new_rt.py, core_old_rt.py]\n')
        with self.assertRaisesRegex(MigratorError, re.escape("disallowed attribute(s) found: {'obj_defs'}")):
            MigrationController.get_migrations_config(temp_bad_config_example)

        with self.assertRaisesRegex(MigratorError, "could not read migration config file: "):
            MigrationController.get_migrations_config(os.path.join(self.fixtures_path, 'no_file.yaml'))

    def test_migrate_from_desc(self):
        migration_descs = MigrationController.get_migrations_config(self.config_file)

        migration_desc = migration_descs['migration']
        migrated_filename = self.get_temp_pathname('migration.xlsx')
        migration_desc.migrated_file = migrated_filename
        migrated_file = MigrationController.migrate_from_desc(migration_desc)
        self.assertEqual(migrated_file, migrated_filename)

        migration_desc = migration_descs['migration_with_renaming']
        round_trip_migrated_xlsx_file = self.get_temp_pathname('round_trip_migrated_xlsx_file.xlsx')
        migration_desc.migrated_file = round_trip_migrated_xlsx_file
        MigrationController.migrate_from_desc(migration_desc)
        existing = read_workbook(migration_desc.existing_file)
        round_trip_migrated = read_workbook(round_trip_migrated_xlsx_file)
        self.assertEqual(existing, round_trip_migrated)

    def test_migrate_from_config(self):
        # MigrationController.migrate_from_config(self.config_file)
        # add migrated_file entries to self.config_file, or load and dump it
        pass

    def test_str(self):
        migration_descs = MigrationController.get_migrations_config(self.config_file)
        name = 'migration_with_renaming'
        migration_desc = migration_descs[name]
        migration_desc_str = str(migration_desc)
        self.assertIn(name, migration_desc_str)
        self.assertIn(str(migration_desc.model_defs_files), migration_desc_str)

    @unittest.skip('skipping')
    def test_wc_lang_migration(self):
        # add to migration:
        #   support filenames related to directory of config file
        # needed to read model file:
        #   path
        #   options
        #   schema validation
        #   model order
        #   implict relationships to add
        #   post-reading validation
        # tests:
        #   X-- create and run Migrator from existing wc_lang core to itself

        wc_lang_model_migrated = self.get_temp_pathname('example-wc_lang-model-migrated.xlsx')
        print('wc_lang_model_migrated', wc_lang_model_migrated)
        migration_desc = MigrationDesc('migrate from existing wc_lang core to itself',
            existing_file=self.wc_lang_model_copy,
            model_defs_files=[self.wc_lang_schema_existing, self.wc_lang_schema_existing, self.wc_lang_schema_existing],
            migrated_file=wc_lang_model_migrated)

        '''
        # profiling:
        out_file = self.get_temp_pathname('profile.out')
        print('out_file', out_file)
        locals = {'MigrationController':MigrationController,
            'migration_desc':migration_desc}
        cProfile.runctx('MigrationController.migrate_over_schema_sequence(migration_desc)',
            {}, locals, filename=out_file)
        profile = pstats.Stats(out_file)
        print("Profile:")
        profile.strip_dirs().sort_stats('cumulative').print_stats(30)
        '''
        migrated_filename = MigrationController.migrate_over_schema_sequence(migration_desc)
        self.assertEqual(migrated_filename, wc_lang_model_migrated)

        # validate
        existing = read_workbook(self.wc_lang_model_copy)
        round_trip_migrated = read_workbook(wc_lang_model_migrated)
        self.assertEqual(existing, round_trip_migrated)


class TestMigrationDesc(MigrationFixtures):

    def setUp(self):
        super().setUp()
        old_2_new_renamed_models, old_2_new_renamed_attributes = MigrationFixtures.get_roundtrip_renaming()
        # since MigrationDesc describes a sequence of migrations, embed these in lists
        self.old_2_new_renamed_models = [old_2_new_renamed_models]
        self.old_2_new_renamed_attributes = [old_2_new_renamed_attributes]
        self.migration_desc = MigrationDesc('name',
            existing_file=self.example_old_rt_model_copy,
            model_defs_files=[self.old_rt_model_defs_path, self.new_rt_model_defs_path],
            renamed_models=self.old_2_new_renamed_models,
            renamed_attributes= self.old_2_new_renamed_attributes)

    def tearDown(self):
        super().tearDown()

    def test_validate(self):
        self.assertFalse(self.migration_desc.validate())
        md = copy.deepcopy(self.migration_desc)
        setattr(md, 'disallowed_attr', 'bad')
        self.assertEqual(md.validate(), ["disallowed attribute(s) found: {'disallowed_attr'}"])

        for attr in MigrationDesc._required_attrs:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, attr, None)
            self.assertEqual(md.validate(), ["missing required attribute '{}'".format(attr)])
        md = copy.deepcopy(self.migration_desc)
        md.model_defs_files = []
        self.assertEqual(md.validate(),
            ["model_defs_files must contain at least 2 model definitions, but it has only 0"])
        for renaming_list in MigrationDesc._renaming_lists:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, renaming_list, [[], []])
            self.assertEqual(md.validate(),
                ["model_defs_files specifies 1 migration(s), but {} contains 2 mapping(s)".format(renaming_list)])
        for renaming_list in MigrationDesc._renaming_lists:
            md = copy.deepcopy(self.migration_desc)
            setattr(md, renaming_list, None)
            self.assertFalse(md.validate())

    def test_standardize(self):
        migration_descs = MigrationController.get_migrations_config(self.config_file)
        md = migration_descs['migration']
        for renaming in MigrationDesc._renaming_lists:
            self.assertEqual(len(getattr(md, renaming)), len(md.model_defs_files) - 1)
        renamed_attributes = [
            [[['Test', 'old_attr'], ['MigratedTest', 'new_attr']]],
            [[['Property', 'new_value'], ['Property', 'value']]]]
        migration_desc = MigrationDesc('name_2',
            model_defs_files=['x'],
            renamed_attributes=renamed_attributes)
        expected_renamed_attributes = [
            [(('Test', 'old_attr'), ('MigratedTest', 'new_attr'))],
            [(('Property', 'new_value'), ('Property', 'value'))]]
        migration_desc.standardize()
        self.assertEqual(migration_desc.renamed_attributes, expected_renamed_attributes)

    def test_get_kwargs(self):
        kwargs = self.migration_desc.get_kwargs()
        self.assertEqual(kwargs['existing_file'], self.example_old_rt_model_copy)
        self.assertEqual(kwargs['model_defs_files'], [self.old_rt_model_defs_path, self.new_rt_model_defs_path])
        self.assertEqual(kwargs['renamed_models'], self.old_2_new_renamed_models)
        self.assertEqual(kwargs['renamed_attributes'], self.old_2_new_renamed_attributes)
        self.assertEqual(kwargs['migrated_file'], None)
        self.migration_desc


class TestRunMigration(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_parse_args(self):
        existing_model_definitions = 'dir/file1.py'
        new_model_definitions = 'dir/file2.py'
        files = 'dir1/m1.xlsx dir1/m1.xlsx'
        cl = "{} {} {}".format(existing_model_definitions, new_model_definitions, files)
        args = RunMigration.parse_args(cli_args=cl.split())
        self.assertEqual(args.existing_model_definitions, existing_model_definitions)
        self.assertEqual(args.new_model_definitions, new_model_definitions)
        self.assertEqual(args.files, files.split())

    def test_main(self):
        args = Namespace(existing_model_definitions=self.old_model_defs_path,
            new_model_definitions=self.new_model_defs_path, files=[self.example_old_model_copy])
        migrated_files = RunMigration.main(args)
        root, ext = os.path.splitext(self.example_old_model_copy)
        self.assertEqual(migrated_files[0], "{}{}{}".format(root, Migrator.MIGRATE_SUFFIX, ext))
