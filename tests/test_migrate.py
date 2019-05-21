""" Test schema migration

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2018-11-18
:Copyright: 2018, Karr Lab
:License: MIT
"""

# todo: speedup migration and unittests; make smaller test data files
# todo: ensure that all tmp files are being deleted
# todo: cleanup use of temp dirs & files
# todo: in TestAutomatedMigration, test multiple files in the automated_migration_config

SPEED_UP_TESTING = False
DONT_DEBUG_ON_CIRCLE = True

from argparse import Namespace
from github import Github
from itertools import chain
from networkx.algorithms.shortest_paths.generic import has_path
from pathlib import Path
from pprint import pprint, pformat
from tempfile import mkdtemp
import capturer
import cement
import copy
import cProfile
import filecmp
import getpass
import git
import github
import inspect
import networkx as nx
import numpy
import os
import pstats
import random
import re
import shutil
import socket
import sys
import tempfile
import time
import unittest
import warnings
import yaml

from .config import core
from obj_model.migrate import (MigratorError, MigrateWarning, SchemaModule, Migrator, MigrationController,
    RunMigration, MigrationSpec, SchemaChanges, AutomatedMigration, GitRepo, VirtualEnvUtil,
    CementControllers)
import obj_model
from obj_model import (BooleanAttribute, EnumAttribute, FloatAttribute, IntegerAttribute,
    PositiveIntegerAttribute, RegexAttribute, SlugAttribute, StringAttribute, LongStringAttribute,
    UrlAttribute, OneToOneAttribute, ManyToOneAttribute, ManyToManyAttribute, OneToManyAttribute,
    RelatedAttribute, TabularOrientation, migrate, obj_math, get_models)
from wc_utils.workbook.io import read as read_workbook
from wc_utils.util.files import remove_silently
from wc_utils.util.misc import internet_connected
from obj_model.expression import Expression
from obj_model.io import TOC_NAME

def make_tmp_dirs_n_small_schemas_paths(test_case):
    test_case.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
    test_case.tmp_dir = mkdtemp()
    # create tmp dir in 'fixtures/migrate/tmp' so it can be accessed from Docker container's host
    test_case.tmp_model_dir = mkdtemp(dir=os.path.join(test_case.fixtures_path, 'tmp'))
    test_case.existing_defs_path = os.path.join(test_case.fixtures_path, 'small_existing.py')
    test_case.migrated_defs_path = os.path.join(test_case.fixtures_path, 'small_migrated.py')
    test_case.small_bad_related_path = os.path.join(test_case.fixtures_path, 'small_bad_related.py')

def make_wc_lang_migration_fixtures(test_case):
    # set up wc_lang migration testing fixtures
    test_case.wc_lang_fixtures_path = os.path.join(test_case.fixtures_path, 'wc_lang_fixture', 'wc_lang')
    test_case.wc_lang_schema_existing = os.path.join(test_case.wc_lang_fixtures_path, 'core.py')
    test_case.wc_lang_schema_modified = os.path.join(test_case.wc_lang_fixtures_path, 'core_modified.py')
    test_case.wc_lang_model_copy = copy_file_to_tmp(test_case, 'example-wc_lang-model.xlsx')
    test_case.wc_lang_no_model_attrs = copy_file_to_tmp(test_case, 'example-wc_lang-model.xlsx')

def copy_file_to_tmp(test_case, name):
    # copy file 'name' to a new dir in the tmp dir and return its pathname
    # 'name' may either be an absolute pathname, or the name of a file in fixtures
    # returns the pathname of the file copy
    basename = name
    if os.path.isabs(name):
        basename = os.path.basename(name)
    tmp_filename = os.path.join(mkdtemp(dir=test_case.tmp_model_dir), basename)
    if os.path.isabs(name):
        shutil.copy(name, tmp_filename)
    else:
        shutil.copy(os.path.join(test_case.fixtures_path, name), tmp_filename)
    return tmp_filename

def temp_pathname(testcase, name):
    # create a pathname for a file called name in new temp dir, which will be discarded by tearDown()
    return os.path.join(mkdtemp(dir=testcase.tmp_model_dir), name)

def make_migrators_in_memory(test_case):

    ### create migrator with renaming that doesn't use models in files
    test_case.migrator_for_error_tests = migrator_for_error_tests = Migrator()

    ### these classes contain migration errors for validation tests ###
    ### existing models
    class RelatedObj(obj_model.Model):
        id = SlugAttribute()
    test_case.RelatedObj = RelatedObj

    class TestExisting(obj_model.Model):
        id = SlugAttribute()
        attr_a = StringAttribute()
        unmigrated_attr = StringAttribute()
        extra_attr_1 = obj_math.NumpyArrayAttribute()
        other_attr = StringAttribute()
    test_case.TestExisting = TestExisting

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
    test_case.NewRelatedObj = NewRelatedObj

    class TestMigrated(obj_model.Model):
        id = SlugAttribute()
        attr_b = IntegerAttribute()
        migrated_attr = BooleanAttribute()
        extra_attr_2 = obj_math.NumpyArrayAttribute()
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
        # ignore MigratorError exception which is tested later
        migrator_for_error_tests.prepare()
    except MigratorError:
        pass

    test_case.migrator_for_error_tests_2 = migrator_for_error_tests_2 = Migrator()
    migrator_for_error_tests_2.existing_defs = migrator_for_error_tests.existing_defs
    migrator_for_error_tests_2.migrated_defs = migrator_for_error_tests.migrated_defs
    ### renaming maps
    migrator_for_error_tests_2.renamed_models = [
        ('TestExisting', 'TestMigrated'),
        ('TestExisting2', 'TestMigrated2')]
    migrator_for_error_tests_2.renamed_attributes = migrator_for_error_tests.renamed_attributes
    try:
        # ignore errors -- they're tested in TestMigration.test_get_inconsistencies
        migrator_for_error_tests_2.prepare()
    except MigratorError:
        pass

    # create migrator with renaming that doesn't use models in files and doesn't have errors
    # existing models
    class GoodRelatedCls(obj_model.Model):
        id = SlugAttribute()
        num = IntegerAttribute()
    test_case.GoodRelatedCls = GoodRelatedCls

    class GoodExisting(obj_model.Model):
        id = SlugAttribute()
        attr_a = StringAttribute() # renamed to attr_b
        unmigrated_attr = StringAttribute()
        np_array = obj_math.NumpyArrayAttribute()
        related = OneToOneAttribute(GoodRelatedCls, related_name='test')
    test_case.GoodExisting = GoodExisting

    class GoodNotMigrated(obj_model.Model):
        id_2 = SlugAttribute()
    test_case.GoodNotMigrated = GoodNotMigrated

    # migrated models
    class GoodMigrated(obj_model.Model):
        id = SlugAttribute()
        attr_b = StringAttribute()
        np_array = obj_math.NumpyArrayAttribute()
        related = OneToOneAttribute(RelatedObj, related_name='test_2')
    test_case.GoodMigrated = GoodMigrated

    test_case.good_migrator = good_migrator = Migrator()
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

def rm_tmp_dirs(test_case):
    # remove a test_case's temp dirs
    shutil.rmtree(test_case.tmp_dir)
    shutil.rmtree(test_case.tmp_model_dir)

def invert_renaming(renaming):
    # invert a list of renamed_models or renamed_attributes
    inverted_renaming = []
    for entry in renaming:
        existing, migrated = entry
        inverted_renaming.append((migrated, existing))
    return inverted_renaming

def assert_differing_workbooks(test_case, existing_model_file, migrated_model_file):
    assert_equal_workbooks(test_case, existing_model_file, migrated_model_file, equal=False)

def assert_equal_workbooks(test_case, existing_model_file, migrated_model_file, equal=True):
    # test whether a pair of model files are identical, or not identical if equal=False
    existing_workbook = read_workbook(existing_model_file)
    migrated_workbook = read_workbook(migrated_model_file)

    if TOC_NAME in existing_workbook:
        existing_workbook.pop(TOC_NAME)
    if TOC_NAME in migrated_workbook:
        migrated_workbook.pop(TOC_NAME)

    if equal:
        if not existing_workbook == migrated_workbook:
            # for debugging
            print("differences between existing_model_file '{}' and migrated_model_file '{}'".format(
                existing_model_file, migrated_model_file))
            print(existing_workbook.difference(migrated_workbook))
        test_case.assertEqual(existing_workbook, migrated_workbook)
    else:
        test_case.assertNotEqual(existing_workbook, migrated_workbook)


class MigrationFixtures(unittest.TestCase):
    """ Reused fixture set up and tear down
    """

    def setUp(self):
        make_tmp_dirs_n_small_schemas_paths(self)
        self.migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        self.migrator._load_defs_from_files()

        self.no_change_migrator = Migrator(self.existing_defs_path, self.existing_defs_path)
        self.no_change_migrator.prepare()

        # copy test models to tmp dir
        self.example_existing_model_copy = copy_file_to_tmp(self, 'example_existing_model.xlsx')
        self.example_existing_rt_model_copy = copy_file_to_tmp(self, 'example_existing_model_rt.xlsx')
        self.example_migrated_model = os.path.join(self.tmp_model_dir, 'example_migrated_model.xlsx')

        dst = os.path.join(self.tmp_model_dir, 'tsv_example')
        self.tsv_dir = shutil.copytree(os.path.join(self.fixtures_path, 'tsv_example'), dst)
        self.tsv_test_model = 'test-*.tsv'
        self.example_existing_model_tsv = os.path.join(self.tsv_dir, self.tsv_test_model)
        # put each tsv in a separate dir so globs don't match erroneously
        self.existing_2_migrated_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)
        self.round_trip_migrated_tsv_file = os.path.join(mkdtemp(dir=self.tmp_model_dir), self.tsv_test_model)

        self.config_file = os.path.join(self.fixtures_path, 'config_rt_migrations.yaml')
        self.bad_migrations_config = os.path.join(self.fixtures_path, 'config_example_bad_migrations.yaml')

        make_migrators_in_memory(self)

        # set up round-trip schema fixtures
        self.existing_rt_model_defs_path = os.path.join(self.fixtures_path, 'small_existing_rt.py')
        self.migrated_rt_model_defs_path = os.path.join(self.fixtures_path, 'small_migrated_rt.py')
        # provide existing -> migrated renaming for the round-trip tests
        self.existing_2_migrated_renamed_models = [('Test', 'MigratedTest')]
        self.existing_2_migrated_renamed_attributes = [
            (('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr')),
            (('Property', 'value'), ('Property', 'migrated_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))]

        make_wc_lang_migration_fixtures(self)

        # set up expressions testing fixtures
        self.wc_lang_no_change_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_existing)
        self.wc_lang_changes_migrator = Migrator(self.wc_lang_schema_existing,
            self.wc_lang_schema_modified, renamed_models=[('Parameter', 'ParameterRenamed')])
        self.no_change_migrator_model = self.set_up_fun_expr_fixtures(
            self.wc_lang_no_change_migrator, 'Parameter', 'Parameter')
        self.changes_migrator_model = \
            self.set_up_fun_expr_fixtures(self.wc_lang_changes_migrator, 'Parameter', 'ParameterRenamed')

        # since MigrationSpec specifies a sequence of migrations, embed renamings in lists
        self.migration_spec = MigrationSpec('name',
            existing_files=[self.example_existing_rt_model_copy],
            schema_files=[self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path],
            seq_of_renamed_models=[self.existing_2_migrated_renamed_models],
            seq_of_renamed_attributes=[self.existing_2_migrated_renamed_attributes])

        # files to delete that are not in a temp directory
        self.files_to_delete = set()

    def set_up_fun_expr_fixtures(self, migrator, existing_param_class, migrated_param_class):
        migrator.prepare()
        Model = migrator.existing_defs['Model']
        # define models in FunctionExpression.valid_used_models
        Function = migrator.existing_defs['Function']
        Observable = migrator.existing_defs['Observable']
        ParameterClass = migrator.existing_defs[existing_param_class]
        objects = {model: {} for model in [ParameterClass, Function, Observable]}
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
        rm_tmp_dirs(self)
        for file in self.files_to_delete:
            remove_silently(file)


@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestSchemaModule(unittest.TestCase):

    def setUp(self):
        make_tmp_dirs_n_small_schemas_paths(self)
        make_wc_lang_migration_fixtures(self)

        self.test_package = os.path.join(self.fixtures_path, 'test_package')
        self.module_for_testing = os.path.join(self.test_package, 'module_for_testing.py')
        self.code = os.path.join(self.test_package, 'pkg_dir', 'code.py')

        # files to delete that are not in a temp directory
        self.files_to_delete = set()

    def tearDown(self):
        rm_tmp_dirs(self)
        for file in self.files_to_delete:
            remove_silently(file)

    def test_parse_module_path(self):
        parse_module_path = SchemaModule.parse_module_path

        # exceptions
        not_a_python_file = os.path.join(self.tmp_dir, 'not_a_python_file.x')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a Python source file name"):
            parse_module_path(not_a_python_file)
        no_such_file = os.path.join(self.tmp_dir, 'no_such_file.py')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            parse_module_path(no_such_file)
        not_a_file = mkdtemp(suffix='.py', dir=self.tmp_dir)
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            parse_module_path(not_a_file)

        # module that's not in a package
        expected_dir = self.fixtures_path
        expected_package = None
        expected_module = 'small_existing'
        self.assertEqual(parse_module_path(self.existing_defs_path),
            (expected_dir, expected_package, expected_module))

        # module in package
        expected_dir = self.fixtures_path
        expected_package = 'test_package'
        expected_module = 'test_package.module_for_testing'
        self.assertEqual(parse_module_path(self.module_for_testing),
            (expected_dir, expected_package, expected_module))

        try:
            # test at /
            # if files cannot be written to / these tests fail silently
            module_in_root = os.path.join('/', os.path.basename(self.existing_defs_path))
            # ensure that module_in_root is removed
            self.files_to_delete.add(module_in_root)
            shutil.copy(self.existing_defs_path, module_in_root)
            expected_dir = '/'
            expected_package = None
            expected_module = 'small_existing'
            self.assertEqual(parse_module_path(module_in_root),
                (expected_dir, expected_package, expected_module))

            # package in /
            self.files_to_delete.add('/__init__.py')
            src_dst_copy_pairs = [
                (os.path.join(self.test_package, '__init__.py'), '/'),
                (os.path.join(self.test_package, '__init__.py'), '/tmp/'),
                (self.existing_defs_path, '/tmp')
            ]
            for src, dst in src_dst_copy_pairs:
                shutil.copy(src, dst)
            module_in_pkg_in_root = os.path.join('/', 'tmp', os.path.basename(self.existing_defs_path))
            expected_dir = '/'
            expected_package = 'tmp'
            expected_module = 'tmp.small_existing'
            self.assertEqual(parse_module_path(module_in_pkg_in_root),
                (expected_dir, expected_package, expected_module))

        except PermissionError:
            pass

    def check_imported_module(self, schema_module, module_name, module):
        """ Check that an imported module has the right models and relationships between them
        """
        self.assertEqual(module_name, module.__name__)

        expected_models = {
            'small_existing': {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'},
            'test_package.module_for_testing': {'Foo', 'Test', 'Reference'},
            'test_package.pkg_dir.code': {'Foo'},
        }

        expected_relationships = {
            'small_existing': [
                (('Property', 'test'), ('Test', 'property')),
                (('Subtest', 'test'), ('Test', 'subtests')),
                (('Subtest', 'references'), ('Reference', 'subtests'))
            ],
            'test_package.module_for_testing': [
                (('Test', 'references'), ('Reference', 'tests')),
            ],
            'test_package.pkg_dir.code': [],
        }

        model_defs = schema_module._get_model_defs(module)
        self.assertEqual(expected_models[module_name], set(model_defs))
        for left, right in expected_relationships[module_name]:
            left_model, left_attr = left
            right_model, right_attr = right
            left_related = getattr(model_defs[left_model], left_attr).related_class
            self.assertEqual(left_related, model_defs[right_model],
                "left_related: {}, model_defs[right_model]: {}".format(id(left_related), id(model_defs[right_model])))
            right_related = model_defs[right_model].Meta.related_attributes[right_attr].related_class
            self.assertEqual(left_related, right_related)

    def multiple_import_tests_of_test_package(self, test_package_dir):
        # test import of test_package and submodules in it

        # import module in a package
        module_for_testing = os.path.join(test_package_dir, 'module_for_testing.py')
        sm = SchemaModule(module_for_testing)
        module = sm.import_module_for_migration()
        self.check_imported_module(sm, 'test_package.module_for_testing', module)
        self.check_related_attributes(sm)

        # import module two dirs down in a package
        code = os.path.join(test_package_dir, 'pkg_dir', 'code.py')
        sm = SchemaModule(code)
        module = sm.import_module_for_migration()
        self.check_imported_module(sm, 'test_package.pkg_dir.code', module)
        self.check_related_attributes(sm)

        # test deletion of imported schemas from sys.modules after importlib.import_module()
        # ensure that the schema and its submodels get deleted from sys.modules
        modules_that_sys_dot_modules_shouldnt_have = [
            'test_package',
            'test_package.pkg_dir',
            'test_package.pkg_dir.code',
            'test_package.module_for_testing',
        ]
        for module in modules_that_sys_dot_modules_shouldnt_have:
            self.assertTrue(module not in sys.modules)

    def test_munging(self):

        class A(obj_model.Model):
            id = SlugAttribute()

            class Meta(obj_model.Model.Meta):
                attribute_order = ('id',)

        name_a = A.__name__
        munged_name_a = SchemaModule._munged_model_name(A)
        self.assertTrue(munged_name_a.startswith(name_a))
        self.assertTrue(munged_name_a.endswith(SchemaModule.MUNGED_MODEL_NAME_SUFFIX))

        A.__name__ = munged_name_a
        self.assertTrue(SchemaModule._model_name_is_munged(A))
        self.assertEqual(SchemaModule._munged_model_name(A), munged_name_a)
        self.assertEqual(SchemaModule._unmunged_model_name(A), name_a)
        A.__name__ = SchemaModule._unmunged_model_name(A)
        self.assertFalse(SchemaModule._model_name_is_munged(A))

        SchemaModule._munge_all_model_names()
        for model in get_models():
            self.assertTrue(SchemaModule._model_name_is_munged(model))
        SchemaModule._unmunge_all_munged_model_names()
        for model in get_models():
            self.assertFalse(SchemaModule._model_name_is_munged(model))

    def check_related_attributes(self, schema_module):
        # ensure that all RelatedAttributes point to Models contained within a module
        module = schema_module.import_module_for_migration()
        model_defs = schema_module._get_model_defs(module)
        model_names = set(model_defs)
        models = set(model_defs.values())

        for model_name, model in model_defs.items():
            for attr_name, local_attr in model.Meta.local_attributes.items():

                if isinstance(local_attr.attr, RelatedAttribute):
                    related_class = local_attr.related_class
                    self.assertIn(related_class.__name__, model_names,
                        "{}.{} references a {}, but it's not a model name in module {}".format(
                            model_name, attr_name, related_class.__name__, module.__name__))
                    self.assertEqual(related_class, model_defs[related_class.__name__],
                        "{}.{} references a {}, but it's not the model in module {}: {} != {}".format(
                            model_name, attr_name, related_class.__name__, module.__name__,
                            id(related_class), id(model_defs[related_class.__name__])))

    def test_import_module_for_migration(self):
        # import copy of schema in single file from a new dir
        copy_of_small_existing = copy_file_to_tmp(self, 'small_existing.py')
        sm = SchemaModule(copy_of_small_existing)
        module = sm.import_module_for_migration()

        self.check_imported_module(sm, 'small_existing', module)
        self.check_related_attributes(sm)

        # importing self.existing_defs_path again returns same module from cache
        self.assertEqual(module, sm.import_module_for_migration())

        # test import from a package
        self.multiple_import_tests_of_test_package(self.test_package)

        # put the package in new dir that's not on sys.path
        test_package_copy = temp_pathname(self, 'test_package')
        shutil.copytree(self.test_package, test_package_copy)
        self.multiple_import_tests_of_test_package(test_package_copy)

        # import a module with a syntax bug
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        sm = SchemaModule(bad_module)
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            sm.import_module_for_migration()

        # import existing wc_lang
        sm = SchemaModule(self.wc_lang_schema_existing)
        self.check_related_attributes(sm)

        # import modified wc_lang
        sm = SchemaModule(self.wc_lang_schema_modified)
        self.check_related_attributes(sm)

        # test a copy of wc_lang
        wc_lang_copy = temp_pathname(self, 'wc_lang')
        shutil.copytree(self.wc_lang_fixtures_path, wc_lang_copy)
        for wc_lang_schema in ['core.py', 'core_modified.py']:
            path = os.path.join(wc_lang_copy, wc_lang_schema)
            sm = SchemaModule(path)
            self.check_related_attributes(sm)

        # test _check_imported_models errors exception
        sm = SchemaModule(self.small_bad_related_path)
        with self.assertRaisesRegex(MigratorError,
            r"\w+\.\w+ references a \w+, but it's not the model in module \w+"):
            sm.import_module_for_migration()

        # import a module that's new and missing an attribute
        module_missing_attr = os.path.join(self.tmp_dir, 'module_missing_attr.py')
        f = open(module_missing_attr, "w")
        f.write('# no code')
        f.close()
        with self.assertRaisesRegex(MigratorError,
            "module in '.+' missing required attribute 'no_such_attribute'"):
            SchemaModule(module_missing_attr).import_module_for_migration(required_attrs=['no_such_attribute'])

        # test exception for bad mod_patterns type
        copy_of_small_existing = copy_file_to_tmp(self, 'small_existing.py')
        sm = SchemaModule(copy_of_small_existing)
        with capturer.CaptureOutput(relay=False) as capture_output:
            with self.assertRaisesRegex(MigratorError,
                "mod_patterns must be an iterator that's not a string"):
                sm.import_module_for_migration(debug=True, mod_patterns=3)
            with self.assertRaisesRegex(MigratorError,
                "mod_patterns must be an iterator that's not a string"):
                sm.import_module_for_migration(debug=True, mod_patterns='hi mom')

        module_with_annotation = os.path.join(self.tmp_dir, 'module_with_annotation.py')
        f = open(module_with_annotation, "w")
        f.write('# no code needed')
        sm = SchemaModule(module_with_annotation, annotation='test_annotation')
        sm.import_module_for_migration(validate=False)
        self.assertEqual('test_annotation', SchemaModule.MODULE_ANNOTATIONS[module_with_annotation])

        # test debug of import_module_for_migration
        wc_lang_copy_2 = temp_pathname(self, 'wc_lang')
        shutil.copytree(self.wc_lang_fixtures_path, wc_lang_copy_2)
        path = os.path.join(wc_lang_copy_2, 'core.py')
        sm = SchemaModule(path)
        with capturer.CaptureOutput(relay=False) as capture_output:
            sm.import_module_for_migration(debug=True, print_code=True, mod_patterns=['obj_model'])
            expected_texts = [
                'import_module_for_migration',
                'SchemaModule.MODULES',
                'importing wc_lang.core',
                'Exceeded max',
                'sys.modules entries matching RE patterns',
                'obj_model',
                'sys.path:',
                'new modules:',
                'wc_lang.wc_lang']
            for expected_text in expected_texts:
                self.assertIn(expected_text, capture_output.get_text())

        # ensure that modules which are not sub-modules of a package remain in sys.modules
        # use module_not_in_test_package, which will be imported by test_package/pkg_dir/code.py
        # 0: ensure that module_not_in_test_package is not in sys.modules
        module_not_in_test_package = os.path.join(self.fixtures_path, 'module_not_in_test_package.py')
        if 'module_not_in_test_package' in sys.modules:
            del sys.modules['module_not_in_test_package']
        self.assertFalse('module_not_in_test_package' in sys.modules)
        # 1: prepare
        # copy module_not_in_test_package.py to a new tmp dir T
        tmp_path_to_module_not_in_test_package = copy_file_to_tmp(self, 'module_not_in_test_package.py')
        # put T on sys.path
        sys.path.append(os.path.dirname(tmp_path_to_module_not_in_test_package))

        # 2: setup test_package to import module_not_in_test_package
        # copy test_package to a new tmp dir that's not on sys.path
        test_package_copy = temp_pathname(self, 'test_package')
        shutil.copytree(self.test_package, test_package_copy)
        # modify core.py in test_package to import module_not_in_test_package
        core_path = os.path.join(test_package_copy, 'pkg_dir', 'code.py')
        with open(core_path, 'a') as f:
            f.write('\nimport module_not_in_test_package')

        # 3: use import_module_for_migration to import test_package.pkg_dir.code, which will
        #    import module_not_in_test_package
        SchemaModule(core_path).import_module_for_migration()

        # 4: confirm that import_module_for_migration() left module_not_in_test_package in sys.modules
        self.assertTrue('module_not_in_test_package' in sys.modules)

        # 5: cleanup: remove module_not_in_test_package from sys.modules, & remove T from sys.path
        del sys.modules['module_not_in_test_package']
        del sys.path[sys.path.index(os.path.dirname(tmp_path_to_module_not_in_test_package))]

    def test_check_imported_models(self):
        for good_schema_path in [self.existing_defs_path, self.migrated_defs_path, self.wc_lang_schema_existing,
            self.wc_lang_schema_modified]:
            sm = SchemaModule(good_schema_path)
            self.assertEqual(sm._check_imported_models(), [])

    def test_get_model_defs(self):
        sm = SchemaModule(self.existing_defs_path)
        module = sm.import_module_for_migration()
        models = sm._get_model_defs(module)
        self.assertEqual(set(models), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(models['Test'].__name__, 'Test')

        # test detection of a module with no Models
        empty_module = os.path.join(self.tmp_dir, 'empty_module.py')
        f = open(empty_module, "w")
        f.write('# a module with no Models')
        f.close()
        sm = SchemaModule(empty_module)
        with self.assertRaisesRegex(MigratorError, r"No subclasses of obj_model\.Model found in '\S+'"):
            sm.import_module_for_migration()

    def test_str(self):
        sm = SchemaModule(self.existing_defs_path)
        for attr in ['module_path', 'abs_module_path', 'module_name']:
            self.assertIn(attr, str(sm))
        self.assertIn(self.existing_defs_path, str(sm))

    def test_run(self):
        sm = SchemaModule(self.existing_defs_path)
        models = sm.run()
        self.assertEqual(set(models), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})


@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestMigrator(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_validate_transformations(self):
        migrator = Migrator()
        self.assertEqual(Migrator._validate_transformations(migrator.transformations), [])

        def a_callable(): pass
        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, a_callable))
        self.assertEqual(Migrator._validate_transformations(migrator.transformations), [])

        migrator = Migrator(transformations=3)
        self.assertIn("transformations should be a dict",
            Migrator._validate_transformations(migrator.transformations)[0])

        migrator = Migrator(transformations={'FOO':3, Migrator.PREPARE_EXISTING_MODELS:2})
        self.assertRegex(Migrator._validate_transformations(migrator.transformations)[0],
            "names of transformations .+ aren't a subset of the supported transformations")

        migrator = Migrator(transformations=dict.fromkeys(Migrator.SUPPORTED_TRANSFORMATIONS, 3))
        errors = Migrator._validate_transformations(migrator.transformations)
        for error in errors:
            self.assertRegex(error, r"value for transformation '.+' is a\(n\) '.+', which isn't callable")

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
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('NotExisting', 'id'),
            (None, None))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'id'),
            ('NewRelatedObj', 'id'))
        self.assertEqual(migrator_for_error_tests._get_mapped_attribute('RelatedObj', 'no_attr'),
            (None, None))

    def test_load_defs_from_files(self):
        migrator = Migrator(self.existing_defs_path, self.migrated_defs_path)
        migrator._load_defs_from_files()
        self.assertEqual(set(migrator.existing_defs), {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        self.assertEqual(set(migrator.migrated_defs), {'Test', 'NewModel', 'Property', 'Subtest', 'Reference'})

    def test_get_migrated_copy_attr_name(self):
        self.assertTrue(self.migrator._get_migrated_copy_attr_name().startswith(
            Migrator.MIGRATED_COPY_ATTR_PREFIX))

    def test_get_inconsistencies(self):
        migrator_for_error_tests = self.migrator_for_error_tests

        inconsistencies = migrator_for_error_tests._get_inconsistencies('NotExistingModel',
            'NotMigratedModel')
        self.assertRegex(inconsistencies[0], "existing model .* not found in")
        self.assertRegex(inconsistencies[1],
            "migrated model .* corresponding to existing model .* not found in")

        class A(object): pass
        migrator_for_error_tests.existing_defs['A'] = A
        migrator_for_error_tests.models_map['A'] = 'X'
        inconsistencies = migrator_for_error_tests._get_inconsistencies('A', 'NewRelatedObj')
        self.assertRegex(inconsistencies[0],
            "type of existing model '.*' doesn't equal type of migrated model '.*'")
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
            r"existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+")

        inconsistencies = migrator_for_error_tests._get_inconsistencies('TestExisting2', 'TestMigrated2')
        self.assertRegex(inconsistencies[0],
            r".+\..+\..+ is '.+', which differs from the migrated value of .+\..+\..+, which is '.+'")
        self.assertRegex(inconsistencies[1],
            r".+\..+\..+ is '.+', which migrates to '.+', but it differs from .+\..+\..+, which is '.+'")

        inconsistencies = self.migrator_for_error_tests_2._get_inconsistencies('TestExisting2',
            'TestMigrated2')
        self.assertRegex(inconsistencies[1],
            r"existing model '.+' is not migrated, but is referenced by migrated attribute .+\..+")

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
        expected_order = ['FirstUnambiguousModel', 'RenamedModel', 'TestModel', 'TestModels',
            'TestModels3', 'NewModel']
        with self.assertWarnsRegex(MigrateWarning,
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
        with self.assertRaisesRegex(MigratorError,
            "'.*' in renamed attributes not a migrated model.attribute"):
            migrator.prepare()
        migrator.renamed_attributes = []

        # triggering inconsistencies in prepare() requires inconsistent schema on disk
        inconsistent_migrated_model_defs_path = os.path.join(self.fixtures_path,
            'small_migrated_inconsistent.py')
        inconsistent_migrator = Migrator(self.existing_defs_path, inconsistent_migrated_model_defs_path)
        inconsistent_migrator._load_defs_from_files()
        with self.assertRaisesRegex(MigratorError,
            r"existing attribute .+\..+ type .+ differs from its migrated attribute .+\..+ type .+"):
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
        migrated_model = self.good_migrator._migrate_model(good_existing_1, self.GoodExisting,
            self.GoodMigrated)
        self.assertEqual(migrated_model.id, id)
        self.assertEqual(migrated_model.attr_b, attr_a_b)
        numpy.testing.assert_equal(migrated_model.np_array, np_array_val)

        id = None
        good_existing_2 = self.GoodExisting(
            id=id,
            attr_a=attr_a_b,
            np_array=np_array_val
        )
        migrated_model = self.good_migrator._migrate_model(good_existing_2, self.GoodExisting,
            self.GoodMigrated)
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

    def test_path_of_migrated_file(self):
        path_of_migrated_file = Migrator.path_of_migrated_file
        tmp_file = temp_pathname(self, 'model.xlsx')
        tmp_dir = os.path.dirname(tmp_file)
        self.assertEqual(tmp_file, path_of_migrated_file(tmp_file, migrate_in_place=True))
        standard_migrated_filename = os.path.join(tmp_dir, 'model' + Migrator.MIGRATE_SUFFIX + '.xlsx')
        self.assertEqual(standard_migrated_filename, path_of_migrated_file(tmp_file))
        migrate_suffix = '_MIGRATED'
        expected_migrated_filename = os.path.join(tmp_dir, 'model' + migrate_suffix + '.xlsx')
        self.assertEqual(expected_migrated_filename, path_of_migrated_file(tmp_file,
            migrate_suffix=migrate_suffix))

    def test_write_migrated_file_exception(self):
        tmp_file = temp_pathname(self, 'model.xlsx')
        tmp_dir = os.path.dirname(tmp_file)
        standard_migrated_filename = os.path.join(tmp_dir, 'model' + Migrator.MIGRATE_SUFFIX + '.xlsx')
        open(standard_migrated_filename, 'a')
        with self.assertRaisesRegex(MigratorError, "migrated file '.*' already exists"):
            self.no_change_migrator.write_migrated_file(None, None, tmp_file)

    def test_migrate_without_changes(self):
        no_change_migrator = self.no_change_migrator
        no_change_migrator.full_migrate(self.example_existing_model_copy,
            migrated_file=self.example_migrated_model)
        ExistingTest = no_change_migrator.existing_defs['Test']
        models = list(no_change_migrator.existing_defs.values())
        # this compares all Models in self.example_existing_model_copy and self.example_migrated_model
        # because it follows the refs from Test
        self.compare_model(ExistingTest, models, self.example_existing_model_copy, self.example_migrated_model)
        assert_equal_workbooks(self, self.example_existing_model_copy, self.example_migrated_model)

        test_suffix = '_MIGRATED_FILE'
        migrated_filename = no_change_migrator.full_migrate(self.example_existing_model_copy,
            migrate_suffix=test_suffix)
        root, _ = os.path.splitext(self.example_existing_model_copy)
        self.assertEqual(migrated_filename, "{}{}.xlsx".format(root, test_suffix))

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
        migrator = Migrator(self.existing_defs_path, self.existing_defs_path,
            transformations=transformations)
        migrator.prepare()
        migrated_file = migrator.full_migrate(self.example_existing_model_copy)

        # test that inverted transformations make no changes
        assert_equal_workbooks(self, self.example_existing_model_copy, migrated_file)

    def test_full_migrate(self):

        # test round-trip existing -> migrated -> existing
        # use schemas without deleted or migrated models so the starting and ending model files are identical
        # but include model and attr renaming so that existing != migrated

        # make existing -> migrated migrator
        existing_2_migrated_migrator = Migrator(self.existing_rt_model_defs_path,
            self.migrated_rt_model_defs_path,
            renamed_models=self.existing_2_migrated_renamed_models,
            renamed_attributes=self.existing_2_migrated_renamed_attributes)
        existing_2_migrated_migrator.prepare()

        # make migrated -> existing migrator
        migrated_2_existing_migrator = Migrator(self.migrated_rt_model_defs_path,
            self.existing_rt_model_defs_path,
            renamed_models=invert_renaming(self.existing_2_migrated_renamed_models),
            renamed_attributes=invert_renaming(self.existing_2_migrated_renamed_attributes))
        migrated_2_existing_migrator.prepare()

        # round trip test of model in tsv file
        # this fails if _strptime is not imported in advance
        existing_2_migrated_migrator.full_migrate(self.example_existing_model_tsv,
            migrated_file=self.existing_2_migrated_migrated_tsv_file)
        migrated_2_existing_migrator.full_migrate(self.existing_2_migrated_migrated_tsv_file,
            migrated_file=self.round_trip_migrated_tsv_file)
        assert_equal_workbooks(self, self.example_existing_model_tsv, self.round_trip_migrated_tsv_file)

        # round trip test of model in xlsx file
        tmp_existing_2_migrated_xlsx_file = os.path.join(self.tmp_model_dir,
            'existing_2_migrated_xlsx_file.xlsx')
        existing_2_migrated_migrator.full_migrate(self.example_existing_rt_model_copy,
            migrated_file=tmp_existing_2_migrated_xlsx_file)
        round_trip_migrated_xlsx_file = migrated_2_existing_migrator.full_migrate(
            tmp_existing_2_migrated_xlsx_file)
        assert_equal_workbooks(self, self.example_existing_rt_model_copy, round_trip_migrated_xlsx_file)

    def run_check_model_test(self, model, model_def, attr_name, default_value):
        # test _check_model() by setting an attribute to its default
        model_copy = model.copy()
        setattr(model_copy, attr_name, default_value)
        self.assertIn("'{}' lack(s) '{}'".format(model_def.__name__, attr_name),
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
        example_migrated_model = temp_pathname(self, 'example_migrated_model.xlsx')
        self.migrator.full_migrate(self.example_existing_model_copy, migrated_file=example_migrated_model)
        # migrate to self.example_existing_model_copy
        self.migrator.full_migrate(self.example_existing_model_copy, migrate_in_place=True)

        # validate
        assert_equal_workbooks(self, example_migrated_model, self.example_existing_model_copy)

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
        self.assertIsInstance(migrator, Migrator)
        self.assertTrue(callable(migrator.transformations[Migrator.PREPARE_EXISTING_MODELS]))

        same_defs_migrator = Migrator.generate_wc_lang_migrator(existing_defs_file=self.wc_lang_schema_existing,
            migrated_defs_file=self.wc_lang_schema_existing)
        same_defs_migrator.prepare()
        # migrate self.wc_lang_no_model_attrs twice with the generate_wc_lang_migrator
        # the 1st migration adds model attributes, & the 2nd tests that they exist
        wc_lang_model_with_model_attrs = same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)
        assert_differing_workbooks(self, self.wc_lang_no_model_attrs, wc_lang_model_with_model_attrs)
        migrated_file = same_defs_migrator.full_migrate(wc_lang_model_with_model_attrs)
        assert_equal_workbooks(self, wc_lang_model_with_model_attrs, migrated_file)

        bad_kwargs = dict(existing_defs_file='existing_defs.py', migrated_defs_file='migrated_defs.py',
            transformations='foo')
        with self.assertRaisesRegex(MigratorError, "'transformations' entry not allowed in kwargs:\\n.+"):
            Migrator.generate_wc_lang_migrator(**bad_kwargs)

        # raise exception for num models != 1 by creating PREPARE_EXISTING_MODELS that deletes the model
        current_prepare_existing_models_fun = same_defs_migrator.transformations[
            Migrator.PREPARE_EXISTING_MODELS]
        def delete_model_and_call_current(migrator, existing_models):
            model_cls = migrator.existing_defs['Model']
            existing_models = [model for model in existing_models if model.__class__ != model_cls]
            current_prepare_existing_models_fun(migrator, existing_models)
        same_defs_migrator.transformations[Migrator.PREPARE_EXISTING_MODELS] = delete_model_and_call_current
        with self.assertRaisesRegex(MigratorError,
            "existing models must have 1 Model instance, but \\d are present"):
            same_defs_migrator.full_migrate(self.wc_lang_no_model_attrs)

    def test_run(self):
        migrated_files = self.no_change_migrator.run([self.example_existing_model_copy])
        assert_equal_workbooks(self, self.example_existing_model_copy, migrated_files[0])

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


@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestMigrationSpec(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_prepare(self):
        try:
            self.migration_spec.prepare()
        except MigratorError:
            self.fail("prepare() raised MigratorError unexpectedly.")

        setattr(self.migration_spec, 'disallowed_attr', 'bad')
        with self.assertRaises(MigratorError):
            self.migration_spec.prepare()

    def test_load(self):
        temp_bad_config_example = os.path.join(self.tmp_dir, 'bad_config_example.yaml')
        with open(temp_bad_config_example, 'w') as file:
            file.write(u'migration:\n')
            file.write(u'    obj_defs: [small_migrated_rt.py, small_existing_rt.py]\n')
        with self.assertRaisesRegex(MigratorError,
            re.escape("disallowed attribute(s) found: {'obj_defs'}")):
            MigrationSpec.load(temp_bad_config_example)

        migration_specs = MigrationSpec.load(self.config_file)
        self.assertIn('migration_with_renaming', migration_specs)

    def test_get_migrations_config(self):
        migration_specs = MigrationSpec.get_migrations_config(self.config_file)
        self.assertIn('migration_with_renaming', migration_specs)

        with self.assertRaisesRegex(MigratorError, "could not read migration config file: "):
            MigrationSpec.get_migrations_config(os.path.join(self.fixtures_path, 'no_file.yaml'))

        # test detecting bad yaml
        bad_yaml = os.path.join(self.tmp_dir, 'bad_yaml.yaml')
        f = open(bad_yaml, "w")
        f.write("unbalanced brackets: ][")
        f.close()
        with self.assertRaisesRegex(MigratorError, r"could not parse YAML migration config file: '\S+'"):
            MigrationSpec.get_migrations_config(bad_yaml)

    def test_validate(self):
        self.assertFalse(self.migration_spec.validate())
        ms = copy.deepcopy(self.migration_spec)
        setattr(ms, 'disallowed_attr', 'bad')
        self.assertEqual(ms.validate(), ["disallowed attribute(s) found: {'disallowed_attr'}"])

        for attr in MigrationSpec._REQUIRED_ATTRS:
            ms = copy.deepcopy(self.migration_spec)
            setattr(ms, attr, None)
            self.assertEqual(ms.validate(), ["missing required attribute '{}'".format(attr)])
            delattr(ms, attr)
            self.assertEqual(ms.validate(), ["missing required attribute '{}'".format(attr)])

        ms = copy.deepcopy(self.migration_spec)
        ms.schema_files = []
        self.assertEqual(ms.validate(),
            ["a migration spec must contain at least 2 schemas, but it has only 0"])

        ms = copy.deepcopy(self.migration_spec)
        ms.git_hashes = ['a'*40]
        error = ms.validate()[0]
        self.assertRegex(error,
            ("a migration spec containing git hashes must have 1 hash for each schema "
                r"file, but this spec has \d git hash\(es\) and \d schemas"))
        ms.git_hashes = ['a'*40, 'a'*40]
        self.assertEqual(ms.validate(), [])

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            ms = copy.deepcopy(self.migration_spec)
            setattr(ms, renaming_list, [[], []])
            error = ms.validate()[0]
            self.assertRegex(error,
                r"{} must have 1 mapping for each of the \d migration.+ specified, but it has \d".format(
                    renaming_list))

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            ms = copy.deepcopy(self.migration_spec)
            setattr(ms, renaming_list, None)
            self.assertFalse(ms.validate())

        for renaming_list in MigrationSpec._CHANGES_LISTS:
            ms = copy.deepcopy(self.migration_spec)
            setattr(ms, renaming_list, [None])
            self.assertEqual(ms.validate(), [])

        bad_renamed_models_examples = [3, [('foo')], [('foo', 1)], [(1, 'bar')]]
        for bad_renamed_models in bad_renamed_models_examples:
            ms = copy.deepcopy(self.migration_spec)
            ms.seq_of_renamed_models = [bad_renamed_models]
            error = ms.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_models must be None, or a list of lists of pairs of strings"))

        bad_renamed_attributes_examples = [
            [[('A', 'att1'), ('B', 'att2', 'extra')]],
            [[('A', 'att1'), ('B')]],
            [[(1, 'att1'), ('B', 'att2')]],
            [[('A', 2), ('B', 'att2')]],
            [3],
            ]
        for bad_renamed_attributes in bad_renamed_attributes_examples:
            ms = copy.deepcopy(self.migration_spec)
            ms.seq_of_renamed_attributes = [bad_renamed_attributes]
            error = ms.validate()[0]
            self.assertTrue(error.startswith(
                "seq_of_renamed_attributes must be None, or a list of lists of pairs of pairs of strings"))

        ms = copy.deepcopy(self.migration_spec)
        ms.existing_files = []
        error = ms.validate()[0]
        self.assertEqual(error, "at least one existing file must be specified")

        ms = copy.deepcopy(self.migration_spec)
        ms.migrated_files = []
        error = ms.validate()[0]
        self.assertRegex(error,
            r"existing_files and migrated_files must .+ but they have \d and \d entries, .+")

        ms.migrated_files = ['file_1', 'file_2']
        error = ms.validate()[0]
        self.assertRegex(error,
            r"existing_files and migrated_files must .+ but they have \d and \d entries, .+")

        ms = copy.deepcopy(self.migration_spec)
        ms.migrator = 'foo'
        error = ms.validate()[0]
        self.assertRegex(error, r"'migrator' must be an element of \{.+\}")

    def test_standardize(self):
        ms = MigrationSpec('name', schema_files=['f1.py', 'f2.py'])
        ms.standardize()
        for renaming in MigrationSpec._CHANGES_LISTS:
            self.assertEqual(getattr(ms, renaming), [None])
        for attr in ['existing_files', 'migrated_files']:
            self.assertEqual(getattr(ms, attr), None)

        migration_specs = MigrationSpec.get_migrations_config(self.config_file)

        ms = migration_specs['simple_migration']
        migrations_config_file_dir = os.path.dirname(ms.migrations_config_file)
        ms.standardize()
        for renaming in MigrationSpec._CHANGES_LISTS:
            self.assertEqual(len(getattr(ms, renaming)), len(ms.schema_files) - 1)
            self.assertEqual(getattr(ms, renaming), [None])
        for file_list in ['existing_files', 'schema_files']:
            for file in getattr(ms, file_list):
                self.assertEqual(os.path.dirname(file), migrations_config_file_dir)

        ms = migration_specs['migration_with_renaming']
        ms.standardize()
        expected_seq_of_renamed_models = [[['Test', 'MigratedTest']], [['MigratedTest', 'Test']]]
        self.assertEqual(ms.seq_of_renamed_models, expected_seq_of_renamed_models)
        expected_1st_renamed_attributes = [
            (('Test', 'existing_attr'), ('MigratedTest', 'migrated_attr')),
            (('Property', 'value'), ('Property', 'migrated_value')),
            (('Subtest', 'references'), ('Subtest', 'migrated_references'))
        ]
        self.assertEqual(ms.seq_of_renamed_attributes[0], expected_1st_renamed_attributes)

        migration_specs = MigrationSpec.get_migrations_config(self.bad_migrations_config)
        ms = migration_specs['migration_with_empty_renaming_n_migrated_files']
        ms.standardize()
        self.assertEqual(ms.seq_of_renamed_attributes[1], None)
        self.assertEqual(os.path.dirname(ms.migrated_files[0]), migrations_config_file_dir)

    def test_expected_migrated_files(self):
        self.assertEqual(self.migration_spec.expected_migrated_files(),
            [Migrator.path_of_migrated_file(self.migration_spec.existing_files[0])])
        ms = copy.deepcopy(self.migration_spec)
        tmp_file = temp_pathname(self, 'model_new.xlsx')
        ms.migrated_files = [tmp_file]
        self.assertEqual(ms.expected_migrated_files(), [tmp_file])

    def test_str(self):
        migration_specs = MigrationSpec.get_migrations_config(self.config_file)
        name = 'migration_with_renaming'
        migration_spec = migration_specs[name]
        migration_spec_str = str(migration_spec)
        self.assertIn(name, migration_spec_str)
        self.assertIn(str(migration_spec.schema_files), migration_spec_str)


@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestMigrationController(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_migrate_over_schema_sequence(self):
        bad_migration_spec = copy.deepcopy(self.migration_spec)
        del bad_migration_spec.migrator
        with self.assertRaises(MigratorError):
            MigrationController.migrate_over_schema_sequence(bad_migration_spec)

        # round-trip test: existing -> migrated -> migrated -> existing
        schema_files = [self.existing_rt_model_defs_path, self.migrated_rt_model_defs_path,
            self.migrated_rt_model_defs_path, self.existing_rt_model_defs_path]
        migrated_2_existing_renamed_models = invert_renaming(self.existing_2_migrated_renamed_models)
        migrated_2_existing_renamed_attributes = invert_renaming(self.existing_2_migrated_renamed_attributes)
        seq_of_renamed_models = [self.existing_2_migrated_renamed_models, [], migrated_2_existing_renamed_models]
        seq_of_renamed_attributes = [self.existing_2_migrated_renamed_attributes, [],
            migrated_2_existing_renamed_attributes]

        migrated_filename = temp_pathname(self, 'example_existing_model_rt_migrated.xlsx')
        migration_spec = MigrationSpec('name',
            existing_files=[self.example_existing_rt_model_copy],
            schema_files=schema_files,
            seq_of_renamed_models=seq_of_renamed_models,
            seq_of_renamed_attributes=seq_of_renamed_attributes,
            migrated_files=[migrated_filename])
        migration_spec.prepare()
        _, migrated_filenames = MigrationController.migrate_over_schema_sequence(migration_spec)
        assert_equal_workbooks(self, self.example_existing_rt_model_copy, migrated_filenames[0])

        self.migration_spec.prepare()
        with self.assertWarnsRegex(UserWarning,
            r"\d+ instance\(s\) of existing model '\S+' lack\(s\) '\S+' non-default value"):
            MigrationController.migrate_over_schema_sequence(self.migration_spec)

    def put_tmp_migrated_file_in_migration_spec(self, migration_spec, name):
        migrated_filename = temp_pathname(self, name)
        migration_spec.migrated_files = [migrated_filename]
        return migrated_filename

    def test_migrate_from_spec(self):
        migration_specs = MigrationSpec.load(self.config_file)

        migration_spec = migration_specs['simple_migration']
        tmp_migrated_filename = self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'migration.xlsx')
        migrated_filenames = MigrationController.migrate_from_spec(migration_spec)
        self.assertEqual(tmp_migrated_filename, migrated_filenames[0])
        assert_equal_workbooks(self, migration_spec.existing_files[0], migrated_filenames[0])

        migration_spec = migration_specs['migration_with_renaming']
        self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'round_trip_migrated_xlsx_file.xlsx')
        round_trip_migrated_xlsx_files = MigrationController.migrate_from_spec(migration_spec)
        assert_equal_workbooks(self, migration_spec.existing_files[0], round_trip_migrated_xlsx_files[0])

        migration_spec = migration_specs['wc_lang_migration']
        self.put_tmp_migrated_file_in_migration_spec(migration_spec, 'example-wc_lang-model_migrated.xlsx')
        round_trip_migrated_wc_lang_files = MigrationController.migrate_from_spec(migration_spec)
        assert_equal_workbooks(self, migration_spec.existing_files[0], round_trip_migrated_wc_lang_files[0])

    def test_migrate_from_config(self):
        # these are round-trip migrations

        # Prepare to remove the migrated_files so they do not contaminate tests/fixtures/migrate.
        # An alternative but more complex approach would be to copy the YAML config file into
        # a temp dir along with the files and directories (packages) it references.
        for migration_spec in MigrationSpec.load(self.config_file).values():
            for expected_migrated_file in migration_spec.expected_migrated_files():
                self.files_to_delete.add(expected_migrated_file)

        results = MigrationController.migrate_from_config(self.config_file)
        for migration_spec, migrated_files in results:
            assert_equal_workbooks(self, migration_spec.existing_files[0], migrated_files[0])

    @unittest.skip("optional performance test")
    def test_migrate_from_config_performance(self):
        # test performance
        for migration_spec in MigrationSpec.load(self.config_file).values():
            for expected_migrated_file in migration_spec.expected_migrated_files():
                self.files_to_delete.add(expected_migrated_file)

        out_file = temp_pathname(self, "profile_out.out")
        locals = {'self':self, 'MigrationController':MigrationController}
        cProfile.runctx('results = MigrationController.migrate_from_config(self.config_file)', {},
            locals, filename=out_file)
        profile = pstats.Stats(out_file)
        print("Profile for 'MigrationController.migrate_from_config(self.config_file)'")
        profile.strip_dirs().sort_stats('cumulative').print_stats(20)

    def test_wc_lang_migration(self):
        # round-trip migrate through changed schema

        # Process for testing a round-trip migration of a wc_lang model that lacks 'model' attributes
        # 1: create model file with 'model' attributes by migrating to tmp file w generate_wc_lang_migrator
        # 2: use the tmp migrated file in a round-trip migration with migrations that invert each other
        fully_instantiated_wc_lang_model = temp_pathname(self, 'fully_instantiated_wc_lang_model.xlsx')
        fully_instantiate_migration = MigrationSpec(
            "1: create fully instantiated model with 'model' attributes: migrate model from existing wc_lang core to itself",
            migrator='wc_lang',
            existing_files=[self.wc_lang_model_copy],
            schema_files=[self.wc_lang_schema_existing, self.wc_lang_schema_existing],
            migrated_files=[fully_instantiated_wc_lang_model])
        fully_instantiate_migration.prepare()
        MigrationController.migrate_over_schema_sequence(fully_instantiate_migration)

        rt_through_changes_migration = MigrationSpec(
            "2: round trip migration with migrations that invert each other",
            existing_files=[fully_instantiated_wc_lang_model],
            schema_files=[self.wc_lang_schema_existing, self.wc_lang_schema_modified,
                self.wc_lang_schema_existing],
            seq_of_renamed_models=[[('Parameter', 'ParameterRenamed')], [('ParameterRenamed', 'Parameter')]])
        rt_through_changes_migration.prepare()
        _, rt_through_changes_wc_lang_models = \
            MigrationController.migrate_over_schema_sequence(rt_through_changes_migration)
        # validate round trip
        assert_equal_workbooks(self, fully_instantiated_wc_lang_model, rt_through_changes_wc_lang_models[0])


class AutoMigrationFixtures(unittest.TestCase):

    @classmethod
    def make_tmp_dir(cls):
        return mkdtemp(dir=cls.tmp_dir)

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = mkdtemp()
        cls.test_repo_url = 'https://github.com/KarrLab/test_repo'
        # get these repos once for the TestCase to speed up tests
        cls.git_repo = GitRepo(cls.test_repo_url)
        cls.known_hash = 'ab34419496756675b6e8499e0948e697256f2698'
        cls.known_hash_ba1f9d3 = 'ba1f9d33a3e18a74f79f41903e7e88e118134d5f'
        cls.hash_commit_tag_ROOT = 'd848093'
        cls.schema_changes_file = SchemaChanges.find_file(cls.git_repo, cls.known_hash_ba1f9d3)

        cls.migration_test_repo_url = 'https://github.com/KarrLab/migration_test_repo'
        cls.migration_test_repo_known_hash = '820a5d1ac8b660b9bdf609b6b71be8b5fdbf8bd3'
        cls.git_migration_test_repo = GitRepo(cls.migration_test_repo_url)
        cls.clean_schema_changes_file = SchemaChanges.find_file(cls.git_migration_test_repo,
            cls.migration_test_repo_known_hash)

        cls.totally_empty_git_repo = GitRepo()
        cls.fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir)
        # remove the GitRepo's temp_dirs
        cls.git_repo.del_temp_dirs()

    def setUp(self):
        # create empty repo containing a commit and a migrations directory
        repo_dir = self.make_tmp_dir()
        repo = git.Repo.init(repo_dir)
        empty_file = os.path.join(repo_dir, 'file')
        open(empty_file, 'wb').close()
        repo.index.add([empty_file])
        repo.index.commit("initial commit")
        self.nearly_empty_git_repo = GitRepo(repo_dir)
        Path(self.nearly_empty_git_repo.migrations_dir()).mkdir()


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestSchemaChanges(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.schema_changes = SchemaChanges(self.git_repo)
        self.test_data = dict(
            commit_hash='a'*40,
            renamed_models=[('Foo', 'FooNew')],
            renamed_attributes=[[('Foo', 'Attr'), ('FooNew', 'AttrNew')]],
            transformations_file=''
        )
        self.empty_schema_changes = SchemaChanges(self.nearly_empty_git_repo)
        self.empty_migrations_dir = self.empty_schema_changes.schema_repo.migrations_dir()

    def test_get_date_timestamp(self):
        timestamp = SchemaChanges.get_date_timestamp()
        # good for 81 years:
        self.assertTrue(timestamp.startswith('20'))
        self.assertEqual(len(timestamp), 19)

    def test_all_schema_changes_files(self):
        files = SchemaChanges.all_schema_changes_files(self.git_repo.migrations_dir())
        self.assertEqual(len(files), 6)
        an_expected_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml')
        self.assertTrue(an_expected_file in files)

        with self.assertRaisesRegex(MigratorError, r"no schema changes files in '\S+'"):
            SchemaChanges.all_schema_changes_files(self.nearly_empty_git_repo.migrations_dir())

    def test_all_schema_changes_with_commits(self):
        all_schema_changes_with_commits = SchemaChanges.all_schema_changes_with_commits
        errors, schema_changes = all_schema_changes_with_commits(self.git_repo)
        self.assertEqual(len(errors), 5)
        self.assertEqual(len(schema_changes), 1)
        self.assertEqual(schema_changes[0].schema_changes_file, self.schema_changes_file)

    def test_find_file(self):
        schema_changes_file = SchemaChanges.find_file(self.git_repo, self.known_hash_ba1f9d3)
        self.assertEqual(os.path.basename(schema_changes_file),
            'schema_changes_2019-02-13-14-05-42_ba1f9d3.yaml')

        with self.assertRaisesRegex(MigratorError, r"no schema changes file in '.+' for hash \S+"):
            SchemaChanges.find_file(self.git_repo, 'not_a_hash_not_a_hash_not_a_hash_not_a_h')

        migrations_dir = self.git_repo.migrations_dir()
        self.schema_changes.make_template(changes_file_dir=migrations_dir)
        time.sleep(2)
        self.schema_changes.make_template(changes_file_dir=migrations_dir)
        with self.assertRaisesRegex(MigratorError,
            r"multiple schema changes files in '.+' for hash \S+"):
            SchemaChanges.find_file(self.git_repo, self.schema_changes.get_hash())

        with self.assertRaisesRegex(MigratorError,
            r"hash prefix in schema changes filename '.+' inconsistent with hash in file: '\S+'"):
            SchemaChanges.find_file(self.git_repo, 'a'*40)

        with self.assertRaisesRegex(MigratorError,
            "the hash in '.+', which is '.+', isn't the hash of a commit"):
            SchemaChanges.find_file(self.git_repo, 'abcdefabcdefabcdefabcdefabcdefabcdefabcd')

    def test_generate_filename(self):
        filename = self.schema_changes.generate_filename()
        self.assertTrue(filename.endswith('.yaml'))
        self.assertTrue(2 <= len(filename.split('_')))

    def test_make_template(self):
        for changes_file_dir in [None, self.empty_migrations_dir]:
            pathname = self.empty_schema_changes.make_template(changes_file_dir=changes_file_dir)
            data = yaml.load(open(pathname, 'r'), Loader=yaml.FullLoader)
            for attr in ['renamed_models', 'renamed_attributes']:
                self.assertEqual(data[attr], [])
            for attr in ['commit_hash', 'transformations_file']:
                self.assertIsInstance(data[attr], str)
            os.remove(pathname)

        schema_changes = SchemaChanges()
        path = schema_changes.make_template(schema_url=self.test_repo_url)
        self.assertTrue(os.path.isfile(path))
        schema_changes_files = SchemaChanges.all_schema_changes_files(
            schema_changes.schema_repo.migrations_dir())
        self.assertIn(path, schema_changes_files)

        path = self.schema_changes.make_template(commit_hash=self.known_hash_ba1f9d3)
        self.assertTrue(os.path.isfile(path))
        schema_changes_files = SchemaChanges.all_schema_changes_files(
            self.schema_changes.schema_repo.migrations_dir())
        self.assertIn(path, schema_changes_files)

        # instantly create two, which will likely have the same timestamp
        pathname = self.empty_schema_changes.make_template(changes_file_dir=self.empty_migrations_dir)
        with self.assertRaisesRegex(MigratorError, "schema changes file '.+' already exists"):
            self.empty_schema_changes.make_template(changes_file_dir=self.empty_migrations_dir)
        os.remove(pathname)

    def test_import_transformations(self):
        find_file = SchemaChanges.find_file
        schema_changes = SchemaChanges.generate_instance(self.schema_changes_file)
        transformations = schema_changes.import_transformations()
        self.assertIsInstance(transformations, dict)
        self.assertEqual(transformations['PREPARE_EXISTING_MODELS'],
            transformations['MODIFY_MIGRATED_MODELS'])

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_no-transformations-file_aaaaaaa.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        transformations = schema_changes.import_transformations()
        self.assertTrue(transformations is None)

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_bad-transformations_ccccccc.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        with self.assertRaisesRegex(MigratorError, "'.+' does not have a 'transformations' attribute"):
            schema_changes.import_transformations()

        schema_changes_file = os.path.join(self.git_repo.migrations_dir(),
            'schema_changes_bad-transformations_bbbbbbb.yaml')
        schema_changes = SchemaChanges.generate_instance(schema_changes_file)
        with self.assertRaisesRegex(MigratorError, "transformations should be a dict, but it is a.+"):
            schema_changes.import_transformations()

    def test_load(self):
        schema_changes = SchemaChanges.load(self.schema_changes_file)
        expected_schema_changes = dict(
            commit_hash=self.known_hash_ba1f9d3,
            renamed_attributes=[],
            renamed_models=[['Test', 'TestNew']],
            schema_changes_file=self.schema_changes_file,
            transformations_file='transformations_ba1f9d3.py'
        )
        self.assertEqual(schema_changes, expected_schema_changes)

        no_such_file = 'no such file'
        with self.assertRaisesRegex(MigratorError, "could not read schema changes file: '.+'"):
            SchemaChanges.load(no_such_file)

        # detect bad yaml
        temp_dir = tempfile.TemporaryDirectory()
        bad_yaml = os.path.join(temp_dir.name, 'bad_yaml.yaml')
        with open(bad_yaml, "w") as f:
            f.write("unbalanced brackets: ][")
        with self.assertRaisesRegex(MigratorError,
            r"could not parse YAML schema changes file: '\S+':"):
            SchemaChanges.load(bad_yaml)

        with open(bad_yaml, "w") as f:
            f.write("wrong_attr: []")
        with self.assertRaisesRegex(MigratorError,
            r"schema changes file '.+' must have a dict with these attributes:"):
            SchemaChanges.load(bad_yaml)

        pathname = self.empty_schema_changes.make_template(changes_file_dir=self.empty_migrations_dir)
        with self.assertRaisesRegex(MigratorError,
            r"schema changes file '.+' is empty \(an unmodified template\)"):
            SchemaChanges.load(pathname)

    def test_validate(self):
        schema_changes_file = os.path.join(self.fixtures_path, 'schema_changes',
            'good_schema_changes_2019-03.yaml')
        self.assertFalse(SchemaChanges.validate(SchemaChanges.load(schema_changes_file)))

        schema_changes_file = os.path.join(self.fixtures_path, 'schema_changes',
            'bad_types_schema_changes_2019-03.yaml')
        schema_changes_kwargs = SchemaChanges.load(schema_changes_file)
        errors = SchemaChanges.validate(schema_changes_kwargs)
        self.assertTrue(any([re.search('commit_hash must be a str', e) for e in errors]))
        self.assertTrue(any([re.search('transformations_file must be a str', e) for e in errors]))
        self.assertTrue(any([re.search("renamed_models .* a list of pairs of strings, but is '.*'$", e)
            for e in errors]))
        self.assertTrue(
            any([re.search('renamed_models .*list of pairs of strings, .* examining it raises', e)
                for e in errors]))
        self.assertTrue(
            any([re.search("renamed_attributes.*list of pairs of pairs of strings, but is '.*'$", e)
                for e in errors]))
        self.assertTrue(
            any([re.search("renamed_attributes.*list of.*but.*'.*',.*examining it raises.*error$", e)
                for e in errors]))

        schema_changes_file = os.path.join(self.fixtures_path, 'schema_changes',
            'short_hash_schema_changes_2019-03.yaml')
        schema_changes_kwargs = SchemaChanges.load(schema_changes_file)
        errors = SchemaChanges.validate(schema_changes_kwargs)
        self.assertRegex(errors[0], "commit_hash is '.*', which isn't the right length for a git hash")

    def test_generate_instance(self):
        temp_dir = tempfile.TemporaryDirectory()
        good_yaml = os.path.join(temp_dir.name, 'good_yaml.yaml')
        with open(good_yaml, "w") as f:
            f.write(yaml.dump(self.test_data))
        schema_changes = SchemaChanges.generate_instance(good_yaml)
        for attr in SchemaChanges._CHANGES_FILE_ATTRS:
            self.assertEqual(getattr(schema_changes, attr), self.test_data[attr])

        schema_changes_file = os.path.join(self.fixtures_path, 'schema_changes',
            'bad_types_schema_changes_2019-03.yaml')
        with self.assertRaises(MigratorError):
            SchemaChanges.generate_instance(schema_changes_file)

    def test_str(self):
        for attr in SchemaChanges._ATTRIBUTES:
            self.assertIn(attr, str(self.schema_changes))


def get_github_api_token():
    config = core.get_config()['obj_model']
    return config['github_api_token']


class RemoteBranch(object):
    """ Make branches on GitHub

    This context manager creates and deletes branches on GitHub, which is convenient for testing
    changes to remote repos, without permanently modifying them. For example,

    .. code-block:: python

        with RemoteBranch(repo_name, test_branch):
            # make some changes to branch `test_branch` of repo `repo_name`
            # clone the branch
            git_repo = GitRepo()
            git_repo.clone_repo_from_url(repo_url, branch=test_branch)
            # test properties of the repo

        # test_branch has been deleted
    """
    ORGANIZATION = 'KarrLab'
    def __init__(self, repo_name, branch_name, delete=True):
        """ Initialize

        Args:
            repo_name (:obj:`str`): name of the repo
            branch_name (:obj:`str`): name of the new branch
        """
        self.repo_name = repo_name
        self.branch_name = branch_name
        self.delete = delete

        self.github = Github(get_github_api_token())
        self.repo = self.github.get_repo("{}/{}".format(self.ORGANIZATION, repo_name))
        master = self.repo.get_branch(branch="master")
        self.head = master.commit

    def make_branch(self):
        """ Make a new branch

        Returns:
            :obj:`github.GitRef.GitRef`: a ref to the new branch
        """
        fully_qualified_ref = "refs/heads/{}".format(self.branch_name)
        self.branch_ref = self.repo.create_git_ref(fully_qualified_ref, self.head.sha)
        if not self.branch_ref:
            raise ValueError("couldn't make branch '{}'".format(branch_name))
        return self.branch_ref

    def delete_branch(self):
        """ Delete the branch """
        self.branch_ref.delete()

    def __enter__(self):
        """ Make a new branch as a context manager

        Returns:
            :obj:`Github.`: a ref to the new branch
        """
        return self.make_branch()

    def __exit__(self, type, value, traceback):
        """ Delete the new branch when exiting the context manager
        """
        if self.delete:
            self.delete_branch()


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestGitRepo(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def make_test_repo(self, name):
        # create a test GitHub repository
        # return its URL
        g = github.Github(get_github_api_token())
        org = g.get_organization('KarrLab')
        org.create_repo(name=name, private=False, auto_init=True)
        return 'https://github.com/KarrLab/{}.git'.format(name)

    def delete_test_repo(self, name):
        g = github.Github(get_github_api_token())
        repo = g.get_repo("KarrLab/{}".format(name))
        repo.delete()

    def delete_test_repos(self, test_repos):
        for repo in test_repos:
            try:
                # trap all exceptions, since the delete might fail
                self.delete_test_repo(repo)
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                pass

    def setUp(self):
        super().setUp()
        self.repo_root = self.git_repo.repo_dir
        self.no_such_hash = 'ab34419496756675b6e8499e0948e697256f2699'
        self.branch_test_repo = 'branch_test_repo'
        self.test_github_repo_name = 'test_repo_1'
        # test_github_repo is only needed by test_add_file_and_commit_changes
        if self._testMethodName == 'test_add_file_and_commit_changes':
            # delete test_github_repo_name so prior failures to delete it won't cause trouble
            self.delete_test_repos([self.test_github_repo_name, self.branch_test_repo])
            self.test_github_repo_url = self.make_test_repo(self.test_github_repo_name)
            self.test_github_repo = GitRepo(self.test_github_repo_url)

    def tearDown(self):
        self.delete_test_repos([self.test_github_repo_name, self.branch_test_repo])

    def test_remote_branch_utils(self):
        self.make_test_repo(self.branch_test_repo)
        test_branch = 'test_branch_x'
        remote_branch = RemoteBranch(self.branch_test_repo, test_branch)
        self.assertTrue(remote_branch.make_branch())
        self.assertFalse(remote_branch.delete_branch())
        with RemoteBranch(self.branch_test_repo, test_branch) as branch_ref:
            self.assertTrue(branch_ref)
        with RemoteBranch(self.branch_test_repo, test_branch):
            pass
        self.delete_test_repo(self.branch_test_repo)

    def test_init(self):
        self.assertIsInstance(self.git_repo.repo, git.Repo)
        self.assertEqual(self.repo_root, self.git_repo.repo_dir)
        self.assertEqual(self.git_repo.original_location, self.test_repo_url)
        git_repo = GitRepo(self.git_repo.repo_dir)
        self.assertIsInstance(git_repo.repo, git.Repo)
        with self.assertRaisesRegex(MigratorError, "instantiating a git.Repo from directory '.+' failed"):
            GitRepo(self.tmp_dir)

        # test search_parent_directories
        git_repo_from_root = GitRepo(repo_location=self.git_migration_test_repo.repo_dir)
        repo_child_dir = os.path.join(self.git_migration_test_repo.repo_dir, 'migration_test_repo')
        git_repo_from_child = GitRepo(repo_location=repo_child_dir, search_parent_directories=True)
        self.assertEqual(git_repo_from_root.repo_dir, git_repo_from_child.repo_dir)
        with self.assertRaisesRegex(MigratorError, "instantiating a git.Repo from directory '.+' failed"):
            GitRepo(repo_location=repo_child_dir, search_parent_directories=False)

    def test_get_temp_dir(self):
        self.assertTrue(os.path.isdir(self.totally_empty_git_repo.get_temp_dir()))

        temp_git_repo = GitRepo()
        temp_git_repo.clone_repo_from_url(self.test_repo_url)
        dirs = [dir for dir in temp_git_repo.temp_dirs]
        self.assertTrue(dirs)
        temp_git_repo.del_temp_dirs()
        for d in dirs:
            self.assertFalse(os.path.isdir(d))

    def test_clone_repo_from_url(self):
        repo, dir = self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url)
        self.assertIsInstance(repo, git.Repo)
        self.assertTrue(os.path.isdir(os.path.join(dir, '.git')))
        repo, dir = self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url,
            directory=self.make_tmp_dir())
        self.assertTrue(os.path.isdir(os.path.join(dir, '.git')))

        # test branch
        test_branch = 'branch_for_test_clone_repo_from_url'
        # make new branch
        with RemoteBranch(self.git_repo.repo_name(), test_branch):

            # clone the branch
            git_repo = GitRepo()
            repo, directory = git_repo.clone_repo_from_url(self.test_repo_url, branch=test_branch)
            self.assertEqual(git_repo.branch, test_branch)
            self.assertTrue(os.path.isdir(directory))

        # cloning branch that no longer exists should raise exception
        with self.assertRaisesRegex(MigratorError, "repo cannot be cloned from"):
            git_repo.clone_repo_from_url(self.test_repo_url, branch=test_branch)

        bad_dir = '/asdfdsf/no such dir'
        with self.assertRaisesRegex(MigratorError, "'.+' is not a directory"):
            self.totally_empty_git_repo.clone_repo_from_url(self.test_repo_url, directory=bad_dir)

        bad_url = 'http://www.ibm.com/nothing_here'
        with self.assertRaisesRegex(MigratorError, "repo cannot be cloned from '.+'"):
            self.totally_empty_git_repo.clone_repo_from_url(bad_url)

    # todo: put in wc_util with unittests
    @staticmethod
    def are_dir_trees_equal(dir1, dir2, ignore=None):
        """ Compare two directories recursively

        Files in directories being compared are considered equal if their names and contents are equal.
        Based on https://stackoverflow.com/a/6681395.

        Args:
            dir1 (:obj:`str`): path of left (first) directory
            dir2 (:obj:`str`): path of right (second) directory
            ignore (:obj:`list`, optional): passed as the `ignore` argument to `filecmp.dircmp()`

        Returns:
            :obj:`bool`: True if `dir1` and `dir2` are the same and no exceptions were raised while
                accessing the directories and files; false otherwise.
        """
        dirs_cmp = filecmp.dircmp(dir1, dir2, ignore=ignore)
        if dirs_cmp.left_only or dirs_cmp.right_only or dirs_cmp.funny_files:
            return False
        _, mismatch, errors =  filecmp.cmpfiles(dir1, dir2, dirs_cmp.common_files, shallow=False)
        if mismatch or errors:
            return False
        for common_dir in dirs_cmp.common_dirs:
            new_dir1 = os.path.join(dir1, common_dir)
            new_dir2 = os.path.join(dir2, common_dir)
            if not TestGitRepo.are_dir_trees_equal(new_dir1, new_dir2, ignore=ignore):
                return False
        return True

    def test_copy(self):
        repo_copy = self.git_migration_test_repo.copy()
        self.assertEqual(repo_copy.latest_hash(), self.git_migration_test_repo.latest_hash())
        self.assertEqual(repo_copy.original_location, self.git_migration_test_repo.original_location)
        self.assertNotEqual(repo_copy.migrations_dir(), self.git_migration_test_repo.migrations_dir())
        self.assertTrue(TestGitRepo.are_dir_trees_equal(self.git_migration_test_repo.repo_dir,
            repo_copy.repo_dir, ignore=[]))

        # checkout an earlier version of the repo
        repo_copy.checkout_commit(self.migration_test_repo_known_hash)
        self.assertNotEqual(repo_copy.latest_hash(), self.git_migration_test_repo.latest_hash())
        repo_copy_copy = repo_copy.copy()
        self.assertEqual(repo_copy.latest_hash(), repo_copy_copy.latest_hash())
        self.assertNotEqual(repo_copy.migrations_dir(), repo_copy_copy.migrations_dir())
        self.assertTrue(TestGitRepo.are_dir_trees_equal(repo_copy.repo_dir, repo_copy_copy.repo_dir, ignore=[]))

        empty_git_repo = GitRepo()
        with self.assertRaisesRegex(MigratorError, "cannot copy an empty GitRepo"):
            empty_git_repo.copy()

    def test_migrations_dir(self):
        self.assertTrue(os.path.isdir(self.git_repo.migrations_dir()))
        self.assertEqual(os.path.basename(self.git_repo.migrations_dir()),
            AutomatedMigration._MIGRATIONS_DIRECTORY)

    def test_fixtures_dir(self):
        self.assertTrue(os.path.isdir(self.git_repo.fixtures_dir()))
        self.assertEqual(os.path.basename(self.git_repo.fixtures_dir()), 'fixtures')

    def test_repo_name(self):
        self.assertEqual(self.git_repo.repo_name(), 'test_repo')
        empty_git_repo = GitRepo()
        self.assertEqual(empty_git_repo.repo_name(), GitRepo._NAME_UNKNOWN)
        tmp_git_repo = GitRepo(self.git_repo.repo_dir)
        self.assertIsInstance(tmp_git_repo.repo_name(), str)

    def test_head_commit(self):
        self.assertIsInstance(self.git_repo.head_commit(), git.objects.commit.Commit)

    def test_latest_hash(self):
        commit_hash = self.nearly_empty_git_repo.latest_hash()
        self.assertIsInstance(commit_hash, str)
        self.assertEqual(len(commit_hash), 40)
        self.assertEqual(commit_hash, self.nearly_empty_git_repo.repo.head.commit.hexsha)

    def test_get_commit(self):
        commit = self.git_repo.get_commit(self.known_hash)
        self.assertIsInstance(commit, git.objects.commit.Commit)
        self.assertEqual(commit, self.git_repo.get_commit(commit))

        # errors
        with self.assertRaisesRegex(MigratorError, "commit_or_hash .* cannot be converted into a commit"):
            self.git_repo.get_commit(self.no_such_hash)
        with self.assertRaisesRegex(MigratorError, "commit_or_hash .* cannot be converted into a commit"):
            self.git_repo.get_commit(1)

    def test_get_commits(self):
        self.assertEqual(self.git_repo.get_commits([]), [])
        commit = self.git_repo.get_commit(self.known_hash)
        commits = self.git_repo.get_commits([self.known_hash, self.known_hash])
        self.assertEqual(commits, [commit, commit])

        # errors
        with self.assertRaisesRegex(MigratorError, "No commit found for .+"):
            self.git_repo.get_commits([self.known_hash, self.no_such_hash, self.no_such_hash])

    def test_commits_as_graph(self):
        commit_DAG = self.git_repo.commits_as_graph()
        self.assertIsInstance(commit_DAG, nx.classes.digraph.DiGraph)
        expected_child_parent_edges = [
            # child -> parent commits in test_repo_url == 'https://github.com/KarrLab/test_repo'
            # commits identified by their tags
            # use 'git log --all --decorate --oneline --graph' to see graph of commits
            ('MERGE_FIRST_N_SECOND', 'SECOND_CLONE_3'),
            ('MERGE_FIRST_N_SECOND', 'FIRST_CLONE_2'),
            ('SECOND_CLONE_3', 'MERGE_SECOND_N_THIRD'),
            ('MERGE_SECOND_N_THIRD', 'THIRD_CLONE_2'),
            ('MERGE_SECOND_N_THIRD', 'SECOND_CLONE_2'),
            ('SECOND_CLONE_2', 'SECOND_CLONE_1'),
            ('THIRD_CLONE_2', 'THIRD_CLONE_1'),
            ('FIRST_CLONE_2', 'FIRST_CLONE_1'),
            ('THIRD_CLONE_1', 'ROOT'),
            ('SECOND_CLONE_1', 'ROOT'),
            ('FIRST_CLONE_1', 'ROOT'),
        ]

        # get tagged commits and the expected commit edges obtained by commits_as_graph()
        tags_to_commits = {}
        for tag in git.refs.tag.TagReference.iter_items(self.git_repo.repo):
            tags_to_commits[str(tag)] = tag.commit
        commits = tags_to_commits.values()
        expected_commit_edges = [(tags_to_commits[child].hexsha, tags_to_commits[parent].hexsha)
            for child, parent in expected_child_parent_edges]

        # obtain actual commit edges for the tagged commits
        actual_commit_edges = []
        for (u, v) in commit_DAG.edges():
            if u in commits and v in commits:
                actual_commit_edges.append((u.hexsha, v.hexsha))
        self.assertEqual(sorted(expected_commit_edges), sorted(actual_commit_edges))

    def test_get_hash(self):
        root_commit = None
        for tag in git.refs.tag.TagReference.iter_items(self.git_repo.repo):
            if str(tag) == 'ROOT':
                root_commit = tag.commit
        if root_commit is None:
            self.fail("Could not find commit with tag ROOT")
        commit_hash = GitRepo.get_hash(root_commit)
        self.assertIsInstance(commit_hash, str)
        self.assertEqual(GitRepo.hash_prefix(commit_hash), self.hash_commit_tag_ROOT)

    def test_checkout_commit(self):
        # copy repo because this checks out earlier commits
        git_repo_copy = self.git_repo.copy()
        git_repo_copy.checkout_commit(git_repo_copy.head_commit())
        self.assertEqual(str(git_repo_copy.repo.head.commit), git_repo_copy.head_commit().hexsha)
        git_repo_copy.checkout_commit(self.known_hash)
        self.assertEqual(git_repo_copy.repo.head.commit.hexsha, self.known_hash)

        with self.assertRaisesRegex(MigratorError, r"checkout of '\S+' to commit '\S+' failed"):
            # checkout of commit from wrong repo will fail
            git_repo_copy.checkout_commit(self.git_migration_test_repo.head_commit())

    @unittest.skipIf(DONT_DEBUG_ON_CIRCLE, "control whether runs on CircleCI")
    def test_add_file_and_commit_changes(self):
        empty_repo = self.test_github_repo.repo
        origin = empty_repo.remotes.origin
        ## instructions from https://gitpython.readthedocs.io/en/stable/tutorial.html?highlight=push#handling-remotes
        # create local branch "master" from remote "master"
        empty_repo.create_head('master', origin.refs.master)
        # set local "master" to track remote "master
        empty_repo.heads.master.set_tracking_branch(origin.refs.master)
        # checkout local "master" to working tree
        empty_repo.heads.master.checkout()
        test_filename = 'new_file.txt'
        new_file = os.path.join(self.test_github_repo.repo_dir, test_filename)
        f = open(new_file, 'w')
        text = '# new_file.txt'
        f.write(text)
        f.close()
        self.test_github_repo.add_file(new_file)
        self.test_github_repo.commit_changes('commit msg')
        rv = origin.push()
        if not rv:
            self.fail('push() failed')

        # confirm that new_file has been added
        clone = GitRepo(self.test_github_repo_url)
        cloned_file = os.path.join(clone.repo_dir, test_filename)
        f = open(cloned_file, 'r')
        self.assertEqual(text, f.read())

        no_such_file = os.path.join(self.test_github_repo.repo_dir, 'no such file')
        with self.assertRaisesRegex(MigratorError, r"adding file '.+' to repo '\S+' failed:"):
            self.test_github_repo.add_file(no_such_file)

        with self.assertRaisesRegex(MigratorError, r"commiting repo '\S+' failed:"):
            self.test_github_repo.commit_changes(2)

    @unittest.skipIf(DONT_DEBUG_ON_CIRCLE, "control whether runs on CircleCI")
    def test_push(self):
        test_branch = 'test_branch_for_test_push'
        # make new branch of existing repo
        with RemoteBranch('test_repo', test_branch):

            # clone the repo
            local_repo = GitRepo()
            local_repo.clone_repo_from_url(self.test_repo_url, branch=test_branch)

            # create a new file & add it to the repo
            test_filename = 'new_file.txt'
            new_file = os.path.join(local_repo.repo_dir, test_filename)
            with open(new_file, 'w') as f:
                content = '# new_file.txt'
                f.write(content)
            self.assertTrue(os.path.isfile(new_file))
            local_repo.repo.index.add([new_file])

            # commit the repo
            local_repo.commit_changes("test commit of 'test_repo':'{}'".format(test_branch))

            # push the repo
            push_result = local_repo.push()

            # clone the new branch again
            another_local_repo = GitRepo()
            another_local_repo.clone_repo_from_url(self.test_repo_url, branch=test_branch)

            # check whether it contains the new file
            another_copy_of_new_file = os.path.join(another_local_repo.repo_dir, test_filename)
            self.assertTrue(os.path.isfile(another_copy_of_new_file))
            with open(another_copy_of_new_file, 'r') as f:
                self.assertEqual(content, f.read())

        # push of an uninitialized GitRepo fails
        empty_repo = GitRepo()
        with self.assertRaisesRegex(MigratorError, "push of repo '\S+' failed"):
            empty_repo.push()

    def check_dependency(self, sequence, DAG):
        # check that sequence satisfies "any nodes u, v with a path u -> ... -> v in the DAG appear in
        # the same order in the sequence"
        sequence.reverse()
        for i in range(len(sequence)):
            u = sequence[i]
            for j in range(i+1, len(sequence)):
                v = sequence[j]
                if has_path(DAG, v, u):
                    self.fail("{} @ {} precedes {} @ {} in sequence, but DAG "
                        "has a path {} -> {}".format(u, i, v, j, v, u))

    # todo: method to convert hash prefix to full hash so we can use short hashes
    def test_get_dependents(self):
        before_splitting = self.git_repo.get_commit('d848093018c0660ea3e4728d3c21f3751a53757f')
        clone_1_commit = self.git_repo.get_commit('35f3eb4fe0ebf8f421958d9300c5de94a40fb70e')
        clone_2_commit = self.git_repo.get_commit('45600a7041ccc45058c6f20e7549106503a5d89c')
        clone_3_commit = self.git_repo.get_commit('2e22e3f14a986e46b98269911fab3ec23fd1b9e3')
        clone_2_n_3_merge_commit = self.git_repo.get_commit('d8c707bbafac64478ff8f5afc3ec4f2eeac6acfa')
        clone2_1_2_n_3_merge_commit = self.git_repo.get_commit('6e703e28bae5d1af7a8441a41c9fa078b272cbfd')
        # map from each commit to the commits above that depend on it
        dependency_map = {
            before_splitting: {clone_1_commit, clone_2_commit, clone_3_commit, clone_2_n_3_merge_commit,
                clone2_1_2_n_3_merge_commit},
            clone_1_commit: {clone2_1_2_n_3_merge_commit},
            clone_2_commit: {clone_2_n_3_merge_commit, clone2_1_2_n_3_merge_commit},
            clone_3_commit: {clone_2_n_3_merge_commit, clone2_1_2_n_3_merge_commit},
            clone_2_n_3_merge_commit: {clone2_1_2_n_3_merge_commit},
            clone2_1_2_n_3_merge_commit: set()
        }
        all_above_commits = set(dependency_map.keys())
        for commit, some_dependents in dependency_map.items():
            all_dependents = self.git_repo.get_dependents(commit)
            self.assertTrue(some_dependents.issubset(all_dependents))
            # all_dependents should not contain any of the above commits not in some_dependents
            self.assertFalse((all_above_commits - some_dependents) & all_dependents)

    def test_commits_in_dependency_consistent_seq(self):
        totally_empty_git_repo = self.totally_empty_git_repo
        # to simplify initial tests of commits_in_dependency_consistent_seq use integers, rather than commits
        single_path_edges = [(2, 1), (3, 2), (4, 3), (5, 4)]
        totally_empty_git_repo.commit_DAG = nx.DiGraph(single_path_edges)
        sequence = totally_empty_git_repo.commits_in_dependency_consistent_seq([4, 1, 2])
        only_possible_sequence = [1, 2, 4]
        self.assertEqual(sequence, only_possible_sequence)

        multi_path_edges = [(2, 1), (3, 2), (7, 3), (8, 7), (4, 2), (6, 4), (5, 4), (6, 5), (7, 6)]
        totally_empty_git_repo.commit_DAG = nx.DiGraph(multi_path_edges)
        n_tests = 20
        for _ in range(n_tests):
            first = 1
            stop = 9
            population = range(first, stop)
            commits_to_migrate = random.sample(population, random.choice(range(2, stop - first + 1)))
            sequence = totally_empty_git_repo.commits_in_dependency_consistent_seq(commits_to_migrate)
            self.check_dependency(sequence, totally_empty_git_repo.commit_DAG)

        # create a topological sort of 5 test_repo commits
        self.git_repo.commit_DAG = self.git_repo.commits_as_graph()
        commits_to_migrate = random.sample(self.git_repo.commit_DAG.nodes, 5)
        sequence = self.git_repo.commits_in_dependency_consistent_seq(commits_to_migrate)
        self.check_dependency(sequence, self.git_repo.commit_DAG)

    def test_str(self):
        empty_git_repo = GitRepo()
        attrs = ['repo_dir', 'repo_url', 'repo', 'commit_DAG', 'git_hash_map', 'temp_dirs']
        for git_repo in [empty_git_repo, self.git_migration_test_repo]:
            v = str(git_repo)
            for a in attrs:
                self.assertIn(a, v)


@unittest.skipUnless(internet_connected(), "Internet not connected")
@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestAutomatedMigration(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def setUp(self):
        self.tmp_model_dir = self.make_tmp_dir()
        self.clean_automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.migration_test_repo_url,
                data_config_file_basename='automated_migration_config-migration_test_repo.yaml'))
        self.clean_automated_migration.validate()
        self.migration_test_repo_fixtures = self.clean_automated_migration.data_git_repo.fixtures_dir()
        self.migration_test_repo_data_file_1 = os.path.join(self.migration_test_repo_fixtures, 'data_file_1.xlsx')
        self.migration_test_repo_data_file_1_hash_prefix = '182289c'
        self.buggy_automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.test_repo_url,
                data_config_file_basename='automated_migration_config-test_repo.yaml'))

        self.wc_lang_model = os.path.join(self.fixtures_path, 'example-wc_lang-model.xlsx')

    def test_make_template_config_file(self):
        path = AutomatedMigration.make_template_config_file(self.git_repo, 'example_test_repo')

        # check the file at path
        data = yaml.load(open(path, 'r'), Loader=yaml.FullLoader)
        for name, config_attr in AutomatedMigration._CONFIG_ATTRIBUTES.items():
            if name == 'migrator':
                self.assertEqual(data[name], MigrationSpec.DEFAULT_MIGRATOR)
                continue
            attr_type, _, _ = config_attr
            if attr_type == 'list':
                self.assertEqual(data[name], [])
            elif attr_type == 'str':
                self.assertEqual(data[name], '')

        kwargs = dict(files_to_migrate=['../tests/fixtures//file1.xlsx',
                                        '../tests/fixtures//file2.xlsx'],
            schema_repo_url='https://github.com//KarrLab/migration_test_repo',
            schema_file='../migration_test_repo/core.py',
            migrator='wc_lang'
        )
        path = AutomatedMigration.make_template_config_file(self.git_repo, 'example_test_repo_2',
            **kwargs)
        data = yaml.load(open(path, 'r'), Loader=yaml.FullLoader)
        self.assertEqual(kwargs, data)

        with self.assertRaisesRegex(MigratorError,
            "automated migration configuration file '.+' already exists"):
            AutomatedMigration.make_template_config_file(self.git_repo, 'example_test_repo')

        remove_silently(path)

    def test_load_config_file(self):
        # read config file with initialized values
        pathname = os.path.join(self.git_migration_test_repo.migrations_dir(),
            'automated_migration_config-migration_test_repo.yaml')
        automated_migration_config = AutomatedMigration.load_config_file(pathname)
        expected_automated_migration_config = dict(
            files_to_migrate=['../tests/fixtures/data_file_1.xlsx'],
            migrator='standard_migrator',
            schema_file='../migration_test_repo/core.py',
            schema_repo_url='https://github.com/KarrLab/migration_test_repo'
        )
        self.assertEqual(automated_migration_config, expected_automated_migration_config)

        # test errors
        with self.assertRaisesRegex(MigratorError, "could not read automated migration config file: .+"):
            AutomatedMigration.load_config_file('no such file')

        bad_yaml = os.path.join(self.tmp_dir, 'bad_yaml.yaml')
        f = open(bad_yaml, "w")
        f.write("unbalanced brackets: ][")
        f.close()
        with self.assertRaisesRegex(MigratorError,
            r"could not parse YAML automated migration config file: '\S+'"):
            AutomatedMigration.load_config_file(bad_yaml)

        # make a config file that's missing an attribute
        saved_config_attributes = AutomatedMigration._CONFIG_ATTRIBUTES.copy()
        del AutomatedMigration._CONFIG_ATTRIBUTES['files_to_migrate']
        config_file = AutomatedMigration.make_template_config_file(self.git_repo, 'test_schema_repo')
        # restore the attribute
        AutomatedMigration._CONFIG_ATTRIBUTES = saved_config_attributes
        with self.assertRaisesRegex(MigratorError, "automated migration config file must have a dict "
            "with the attributes in AutomatedMigration._CONFIG_ATTRIBUTES: .+"):
            AutomatedMigration.load_config_file(config_file)
        remove_silently(config_file)

        config_file = AutomatedMigration.make_template_config_file(self.git_repo, 'test_schema_repo')
        with self.assertRaisesRegex(MigratorError,
            "all attributes in an automated migration config file must be initialized, but they are:.+"):
            AutomatedMigration.load_config_file(config_file)
        remove_silently(config_file)

    def test_init(self):
        config_basename = 'automated_migration_config-migration_test_repo.yaml'
        automated_migration = AutomatedMigration(
            **dict(data_repo_location=self.migration_test_repo_url, data_config_file_basename=config_basename))
        self.assertEqual(automated_migration.data_repo_location, self.migration_test_repo_url)
        self.assertEqual(automated_migration.data_config_file_basename, config_basename)
        self.assertEqual(automated_migration.data_git_repo.repo_name(), 'migration_test_repo')
        self.assertIsInstance(automated_migration.data_config, dict)
        self.assertEqual(automated_migration.schema_git_repo.repo_name(), 'migration_test_repo')

        with self.assertRaisesRegex(MigratorError, "initialization of AutomatedMigration must provide "
            r"AutomatedMigration._REQUIRED_ATTRIBUTES (.+) but these are missing: \{'data_config_file_basename'\}"):
            AutomatedMigration(**dict(data_repo_location=self.migration_test_repo_url))

    def test_clean_up(self):
        all_tmp_dirs = []
        for git_repo in self.clean_automated_migration.git_repos:
            all_tmp_dirs.extend(git_repo.temp_dirs)
        for d in all_tmp_dirs:
            self.assertTrue(os.path.isdir(d))
        self.clean_automated_migration.clean_up()
        for d in all_tmp_dirs:
            self.assertFalse(os.path.isdir(d))

    def test_validate(self):
        expected_files_to_migrate = [self.migration_test_repo_data_file_1]
        self.assertEqual(expected_files_to_migrate, self.clean_automated_migration.data_config['files_to_migrate'])
        self.assertEqual(self.clean_automated_migration.data_config['schema_repo_url'],
            'https://github.com/KarrLab/migration_test_repo')
        loaded_schema_changes = self.clean_automated_migration.loaded_schema_changes
        self.assertEqual(len(loaded_schema_changes), 2)
        for change in loaded_schema_changes:
            self.assertIsInstance(change, SchemaChanges)

        # test errors
        os.rename(  # create an error in all_schema_changes_with_commits()
            os.path.join(self.clean_automated_migration.schema_git_repo.migrations_dir(),
                'schema_changes_2019-03-26-20-16-45_820a5d1.yaml'),
            os.path.join(self.clean_automated_migration.schema_git_repo.migrations_dir(),
                'schema_changes_2019-02-13-14-05-42_badhash.yaml'))
        with self.assertRaises(MigratorError):
            self.clean_automated_migration.validate()

        remove_silently(expected_files_to_migrate[0])   # delete a file to migrate
        with self.assertRaisesRegex(MigratorError,
            "file to migrate '.+', with full path '.+', doesn't exist"):
            self.clean_automated_migration.validate()

    def test_get_name(self):
        self.assertIn('automated-migration:migration_test_repo:migration_test_repo:',
            self.clean_automated_migration.get_name())

        self.clean_automated_migration.data_git_repo = None
        with self.assertRaisesRegex(MigratorError,
            re.escape("To run get_name() data_git_repo and schema_git_repo must be initialized")):
            self.clean_automated_migration.get_name()

    def test_get_metadata_model(self):
        self.assertEqual(self.clean_automated_migration.metadata_model, None)
        metadata_model = self.clean_automated_migration.get_metadata_model()
        self.assertTrue(self.clean_automated_migration.metadata_model is not None)
        self.assertEqual(metadata_model.type.__name__, 'GitMetadata')
        self.assertEqual(metadata_model.version_attr, 'revision')

    def test_get_data_file_git_commit_hash(self):
        git_commit_hash = self.clean_automated_migration.get_data_file_git_commit_hash(
            self.migration_test_repo_data_file_1)
        self.assertTrue(git_commit_hash.startswith(self.migration_test_repo_data_file_1_hash_prefix))

        # test exceptions
        with self.assertRaisesRegex(MigratorError, "module in '.+' missing required attribute '_GIT_METADATA'"):
            self.buggy_automated_migration.get_data_file_git_commit_hash('no_file')

        automated_migration_w_bad_data_file_1 = AutomatedMigration(data_repo_location=self.test_repo_url,
            data_config_file_basename='automated_migration_config-test_repo_bad_git_metadata_model.yaml')
        test_repo_fixtures = automated_migration_w_bad_data_file_1.data_git_repo.fixtures_dir()
        test_file = os.path.join(test_repo_fixtures, 'bad_data_file.xlsx')
        with self.assertRaisesRegex(MigratorError, "GitMetadataModel '.*' contains related attributes"):
            automated_migration_w_bad_data_file_1.get_data_file_git_commit_hash(test_file)

        automated_migration_w_bad_data_file_2 = AutomatedMigration(data_repo_location=self.test_repo_url,
            data_config_file_basename='automated_migration_config-test_repo_good_schema.yaml')
        test_file = os.path.join(test_repo_fixtures, 'bad_data_file_2.xlsx')
        with self.assertRaisesRegex(MigratorError,
            "data file '.*' must contain .*instance of .*, the Model containing the git metadata"):
            automated_migration_w_bad_data_file_2.get_data_file_git_commit_hash(test_file)

    def test_generate_migration_spec(self):
        migration_spec = self.clean_automated_migration.generate_migration_spec(
            self.migration_test_repo_data_file_1,
            [SchemaChanges.generate_instance(self.clean_schema_changes_file)])
        self.assertEqual(migration_spec.migrator, 'standard_migrator')
        self.assertEqual(migration_spec.existing_files[0], self.migration_test_repo_data_file_1)
        self.assertEqual(len(migration_spec.schema_files), 2)
        self.assertEqual(len(migration_spec.git_hashes), 2)
        self.assertTrue(migration_spec.git_hashes[0].startswith(
            self.migration_test_repo_data_file_1_hash_prefix))
        self.assertEqual(migration_spec.migrate_in_place, True)
        self.assertEqual(migration_spec._prepared, True)

        # test error
        seq_of_schema_changes = []
        with self.assertRaises(MigratorError):
            self.clean_automated_migration.generate_migration_spec(self.migration_test_repo_data_file_1,
                seq_of_schema_changes)

    def test_schema_changes_for_data_file(self):
        schema_changes = self.clean_automated_migration.schema_changes_for_data_file(
            self.migration_test_repo_data_file_1)
        commit_descs_related_2_migration_test_repo_data_file_1 = [
            # tag, hash prefix
            ('MODIFY_SCHEMA_on_master', '820a5d1'),
        ]
        for sc, commit_desc in zip(schema_changes, commit_descs_related_2_migration_test_repo_data_file_1):
            _, hash_prefix = commit_desc
            self.assertEqual(GitRepo.hash_prefix(sc.commit_hash), hash_prefix)

    def test_prepare(self):
        self.assertEqual(None, self.clean_automated_migration.prepare())
        self.assertEqual(
            [ms.existing_files[0] for ms in self.clean_automated_migration.migration_specs],
            self.clean_automated_migration.data_config['files_to_migrate'])

    def test_verify_schemas(self):
        errors = self.clean_automated_migration.verify_schemas()
        self.assertEqual(errors, [])

    def round_trip_automated_migrate(self, automated_migration):
        # test a round-trip migration
        # since migrates in-place, save existing file for comparison
        existing_file = automated_migration.data_config['files_to_migrate'][0]
        existing_file_copy = copy_file_to_tmp(self, existing_file)
        migrated_files, new_temp_dir = automated_migration.automated_migrate()
        assert_equal_workbooks(self, existing_file_copy, migrated_files[0])
        shutil.rmtree(new_temp_dir)

    def test_automated_migrate(self):
        # test round-trip
        self.round_trip_automated_migrate(self.clean_automated_migration)

        # provide dir for automated_migrate()
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            automated_migration_from_url = AutomatedMigration(
                **dict(data_repo_location=self.migration_test_repo_url,
                    data_config_file_basename='automated_migration_config-migration_test_repo.yaml'))
            migrated_files, temp_dir = automated_migration_from_url.automated_migrate(tmp_dir=tmp_dir_name)
            for migrated_file in migrated_files:
                self.assertTrue(os.path.isfile(migrated_file))
            self.assertEqual(temp_dir, tmp_dir_name)

        # test with pre-existing repo
        migration_test_repo = self.git_migration_test_repo.copy()
        automated_migration_existing_repo = AutomatedMigration(
            **dict(data_repo_location=migration_test_repo.repo_dir,
                data_config_file_basename='automated_migration_config-migration_test_repo.yaml'))
        migrated_files, _ = automated_migration_existing_repo.automated_migrate()
        for migrated_file in migrated_files:
            self.assertTrue(os.path.isfile(migrated_file))

        # test distinct data and schema repos
        # data file in test_repo and schema in migration_test_repo
        test_repo_copy = self.git_repo.copy()
        automated_migration_separate_data_n_schema_repos = AutomatedMigration(
            **dict(data_repo_location=test_repo_copy.repo_dir,
                data_config_file_basename='automated_migration_config-migration_test_repo.yaml'))
        automated_migration_separate_data_n_schema_repos.prepare()
        existing_file = automated_migration_separate_data_n_schema_repos.data_config['files_to_migrate'][0]
        basename = os.path.basename(existing_file)
        existing_file_copy = os.path.join(mkdtemp(dir=self.tmp_dir), basename)
        shutil.copy(existing_file, existing_file_copy)
        migrated_files, _ = automated_migration_separate_data_n_schema_repos.automated_migrate()
        assert_equal_workbooks(self, existing_file_copy, migrated_files[0])

    def test_migrate_files(self):
        test_repo_copy = self.git_repo.copy()
        config_file_path, migrated_files = AutomatedMigration.migrate_files(
            'https://github.com/KarrLab/migration_test_repo/blob/master/migration_test_repo/core.py',
            test_repo_copy.repo_dir,
            ['tests/fixtures/data_file_1.xlsx',
                os.path.join(test_repo_copy.repo_dir, 'tests/fixtures/data_file_1.xlsx')])
        '''
        # todo: fix
        file_copy = os.path.join(os.path.dirname(migrated_files[0]), 'data_file_1_cp.xlsx')
        for migrated_file in migrated_files:
            assert_equal_workbooks(self, file_copy, migrated_file)
        self.assertTrue(os.path.isfile(config_file_path))
        remove_silently(config_file_path)
        '''

        with self.assertRaisesRegex(MigratorError, "schema_url must be URL for python schema"):
            AutomatedMigration.migrate_files('github.com/KarrLab/core.py', '', [])

        with self.assertRaisesRegex(MigratorError, "schema_url must be URL for python schema"):
            AutomatedMigration.migrate_files('https://github.com/core.py', '', [])

        with self.assertRaisesRegex(MigratorError, "schema_url must be URL for python schema"):
            AutomatedMigration.migrate_files('https://github.com/a/b/c/d/e/core', '', [])

        with self.assertRaisesRegex(MigratorError, "local_dir is not a directory"):
            AutomatedMigration.migrate_files('https://github.com/a/b/blob/d/e/core.py', 'foo', [])

        with self.assertRaisesRegex(MigratorError, "cannot find data file"):
            AutomatedMigration.migrate_files('https://github.com/a/b/blob/d/e/core.py',
                '/root/host/Documents/wc_dev_repos/test_repo',
                ['tests/fixtures/not_a_data_file_1.xlsx'])

    def test_str(self):
        str_val = str(self.clean_automated_migration)
        for attr in AutomatedMigration._ATTRIBUTES:
            self.assertRegex(str_val, "{}: .+".format(attr))


@unittest.skipIf(SPEED_UP_TESTING, "skip to speedup testing")
class TestRunMigration(MigrationFixtures):

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_parse_args(self):
        cl = "{}".format(self.config_file)
        args = RunMigration.parse_args(cli_args=cl.split())
        self.assertEqual(args.migrations_config_file, self.config_file)

    def test_main(self):
        for warnings in [True, False]:
            # Prepare to remove the migrated_files if the test fails
            for migration_spec in MigrationSpec.load(self.config_file).values():
                for expected_migrated_file in migration_spec.expected_migrated_files():
                    self.files_to_delete.add(expected_migrated_file)

            args = Namespace(migrations_config_file=self.config_file, warnings=warnings)
            with capturer.CaptureOutput(relay=False) as capture_output:
                results = RunMigration.main(args)
                for migration_disc, migrated_filenames in results:
                    self.assertIn(migration_disc.name, capture_output.get_text())
                    for migrated_file in migrated_filenames:
                        self.assertIn(migrated_file, capture_output.get_text())

            for migration_disc, migrated_filenames in results:
                self.assertIsInstance(migration_disc, MigrationSpec)
                for migrated_file in migrated_filenames:
                    self.assertTrue(os.path.isfile(migrated_file))

            # remove the migrated files so they do not contaminate tests/fixtures/migrate
            for _, migrated_filenames in results:
                for migrated_file in migrated_filenames:
                    remove_silently(migrated_file)


# todo: perhaps move GitRepo, RepoTestingContext and RemoteBranch to wc_utils
# todo: automatically delete the tmp dirs storing clones of a git repo made by RepoTestingContext.__exit__
# could do this with a tempfile.TemporaryDirectory context and GitRepo as a context that takes a tmp dir
class RepoTestingContext(object):
    """ A context for testing modifications to a repo hosted on a git server

    Entering a `RepoTestingContext` clones a branch of a repo, and returns a `GitRepo` of the clone.
    Code in the `with` suite can then modify the repo.
    Exiting the `RepoTestingContext` commits the changes, pushes them to the remote repo,
    clones the repo's branch to a temporary location, and returns a handle to this new clone.
    After exiting the context's `with` block, code can then test the changes that were made.

    To test changes to a GitHub repo *without* permanently modifying the repo,
    a `RepoTestingContext` can be enclosed in a RemoteBranch context. The RemoteBranch initially
    create a new branch of the GitHub repo for the test, and deletes the new branch upon exit.

    Attributes:
        repo_url (:obj:`str`): URL of the repo being changed in the test
        branch_name (:obj:`str`): the repo's branch being tested
        properties (:obj:`dict`): a `dict` used by the context to return results after `__exit__`;
            the repo's cloned branch is provided by `__exit__` as `properties[clone_of_push]`
        clone_of_push (:obj:`str`): key for the repo's cloned branch is provided by `__exit__`;
            default is `clone_of_push`
    """
    CLONE_OF_PUSH = 'clone_of_push'

    def __init__(self, repo_url, branch_name, properties, clone_of_push=CLONE_OF_PUSH):
        """ Initialize a RepoTestingContext

        Raises:
            :obj:`MigratorError`: if `properties` isn't a `dict`
        """
        if not isinstance(properties, dict):
            raise MigratorError("properties must be a dict, but it is a(n) '{}'".format(
                type(properties).__name__))
        self.repo_url = repo_url
        self.branch_name = branch_name
        self.properties = properties
        self.clone_of_push = clone_of_push

    def __enter__(self):
        """ Clone the repo

        Returns:
            :obj:`GitRepo`: local clone of the repo
        """
        self.local_repo = GitRepo()
        self.local_repo.clone_repo_from_url(self.repo_url, branch=self.branch_name)
        return self.local_repo

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Prepare for testing the modified repo

        Commit the repo, push it to the git server, and create a new clone of it;
        the repo's cloned branch is provided by as element `clone_of_push` of the dict
        `properties` provided when `RepoTestingContext` was initialized
        """
        self.local_repo.commit_changes("test commit of branch '{}' of '{}'".format(
            self.branch_name, self.repo_url))

        # push the repo
        push_result = self.local_repo.push()

        # delete the temp dir holding self.local_repo
        self.local_repo.del_temp_dirs()

        # clone the new branch again
        another_local_repo = GitRepo()
        another_local_repo.clone_repo_from_url(self.repo_url, branch=self.branch_name)
        self.properties[self.clone_of_push] = another_local_repo


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestRepoTestingContext(AutoMigrationFixtures):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    @unittest.skipIf(DONT_DEBUG_ON_CIRCLE, "control whether runs on CircleCI")
    def test_repo_testing_context(self):
        test_branch = 'branch_for_testing_repo_testing_context'
        with RemoteBranch(self.git_repo.repo_name(), test_branch):
            properties = {}
            clone_key = 'test_repo_clone'
            with RepoTestingContext(self.test_repo_url, test_branch, properties, clone_key) as local_repo:
                self.assertTrue(isinstance(local_repo, GitRepo))
                self.assertFalse(properties)
                self.assertEqual(local_repo.repo_url, self.test_repo_url)
                self.assertEqual(local_repo.branch, test_branch)
                self.assertTrue(os.path.isdir(local_repo.repo_dir))

            self.assertTrue(clone_key in properties)
            self.assertTrue(isinstance(properties[clone_key], GitRepo))
            new_clone = properties[clone_key]
            self.assertEqual(new_clone.repo_url, self.test_repo_url)
            self.assertEqual(new_clone.branch, test_branch)
            self.assertFalse(os.path.isdir(local_repo.repo_dir))
        new_clone.del_temp_dirs()

        with self.assertRaisesRegex(MigratorError, "properties must be a dict, but it is a"):
            RepoTestingContext(self.test_repo_url, test_branch, 2, '')


class App(cement.App):
    """ Define App to facilitate testing. """
    class Meta:
        label = 'obj-model'
        base_controller = 'base'
        handlers = [
            CementControllers.SchemaChangesTemplateController,
            CementControllers.AutomatedMigrationConfigController,
            CementControllers.TestMigrationController,
            CementControllers.MigrateController,
            CementControllers.MigrateFileController
        ]


@unittest.skipUnless(internet_connected(), "Internet not connected")
@unittest.skipIf(DONT_DEBUG_ON_CIRCLE, "control whether runs on CircleCI")
class TestCementControllers(AutoMigrationFixtures):

    def test_make_changes_template(self):
        test_branch = 'branch_for_test_make_changes_template'
        with RemoteBranch(self.git_repo.repo_name(), test_branch):

            argv = ['make-changes-template', self.test_repo_url, '--branch', test_branch]
            with App(argv=argv) as app:
                with capturer.CaptureOutput(relay=False) as captured:
                    app.run()
                    self.assertIn('template schema changes file created in', captured.get_text())
                    match = re.search("/([^'/]+)'$", captured.get_text())
                    if not match:
                        self.fail("couldn't find schema changes filename in captured output")
                    template_name = match.group(1)

            # before the branch is deleted, check that template schema changes file was made and pushed
            local_repo = GitRepo()
            local_repo.clone_repo_from_url(self.test_repo_url, branch=test_branch)
            # ensure that the template file exists
            template_pathname = os.path.join(local_repo.migrations_dir(), template_name)
            self.assertTrue(os.path.isfile(template_pathname))
            # delete the temp dir holding self.local_repo
            local_repo.del_temp_dirs()

            # check that illegal arguments produce reasonable errors
            NO_SUCH_REPO = 'NO_SUCH_REPO'
            argv = ['make-changes-template', NO_SUCH_REPO]
            with App(argv=argv) as app:
                with capturer.CaptureOutput() as captured:
                    with self.assertRaisesRegex(MigratorError,
                        "repo cannot be cloned from '{}'".format(NO_SUCH_REPO)):
                        app.run()

    @unittest.skip("not finished")
    def test_make_migration_config_file(self):
        test_branch = 'branch_for_test_make_migration_config_file'
        with RemoteBranch(self.git_repo.repo_name(), test_branch):

            argv = ['make-migration-config-file', self.test_repo_url, '--branch', test_branch]
            with App(argv=argv) as app:
                with capturer.CaptureOutput(relay=False) as captured:
                    app.run()


    def test_test_migrations(self):
        pass

    def test_migrate_configured_data_files(self):
        pass

    def test_migrate_data(self):
        pass

    def test_(self):
        pass


@unittest.skip("INCOMPLETE: not finished")
@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestVirtualEnvUtil(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = mkdtemp()
        self.test_virt_env_util = VirtualEnvUtil('test', dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_init(self):
        virt_env_util_1 = VirtualEnvUtil('test_name')
        virt_env_util_2 = VirtualEnvUtil('test_name', dir=self.tmp_dir)
        for virt_env_util in [virt_env_util_1, virt_env_util_2]:
            self.assertEqual(virt_env_util.name, 'test_name')
            self.assertTrue(os.path.isdir(virt_env_util.virtualenv_dir))
            self.assertTrue(isinstance(virt_env_util.env, VirtualEnvironment))

        with self.assertRaisesRegex(ValueError, "name '.*' may not contain whitespace"):
            VirtualEnvUtil('name with\twhitespace')

    def test_is_installed(self):
        pass

    def run_and_check_install(self, pip_spec, package, debug=False):
        # run and check pip's installation of a package
        if debug:
            print('installing', pip_spec, end='')
        start = time.time()
        self.test_virt_env_util.install_from_pip_spec(pip_spec)
        duration = time.time() - start
        if debug:
            print(" took {0:.1f} sec".format(duration))
        self.assertTrue(self.test_virt_env_util.is_installed(package))
        # todo: check that the package has the right version (esp. if hash specified) & can be used

    def test_install_from_pip_spec(self):
        # test PyPI package
        self.run_and_check_install('six', 'six')
        # test PyPI package with version
        self.run_and_check_install('django==1.4', 'django')
        # test WC egg
        self.run_and_check_install('git+https://github.com/KarrLab/log.git#egg=log', 'log')
        # test WC URL commit specified by hash
        self.run_and_check_install(
            'git+git://github.com/KarrLab/wc_onto.git@ced0ba452bbdf332c9f687b78c2fedc68c666ff2', 'wc-onto')
        # test wc_lang commit
        self.run_and_check_install(
            'git+git://github.com/KarrLab/wc_lang.git@6f1d13ea4bafac443a4fcee3e97a85874fd6bd04', 'wc-lang')
        # as of 4/19, https://pip.pypa.io/en/latest/reference/pip_install/#git describes pip package spec. forms for git

    def test_activate_and_deactivate(self):
        pass

    def test_install_from_pip_spec_exception(self):
        pass

    def test_destroy_and_destroyed(self):
        virt_env_util = VirtualEnvUtil('test_name')
        self.assertTrue(os.path.isdir(virt_env_util.virtualenv_dir))
        virt_env_util.destroy()
        self.assertFalse(os.path.isdir(virt_env_util.virtualenv_dir))
        self.assertTrue(virt_env_util.destroyed())
