'''
test plan:
    reread the relevant parts of importlib
    make small, complete test package
        schema defines some obj_model classes
        schema defines classes that inherit from obj_model.Model, and Models that use them
        schema module uses relative imports to load other modules in package
        all these modules use absolute imports
    automate tests with unittest
    test in order:
        parse_module_path()
        import_module_for_migration
        load two small schemas
        load two wc_lang schemas
'''

import os
import errno
import unittest
import inspect
import sys
from tempfile import mkdtemp
import shutil

import obj_model
from obj_model.play_w_import import MigrationSchemaModule, MigratorError

def prt_path():
    print('sys.path:')
    for i, path in enumerate(sys.path):
        print('{}: {}'.format(i, path))

def prt_modules():
    print('sys.modules:')
    for name in sorted(sys.modules):
        module = sys.modules[name]
        print('{}:'.format(name))
        for attr in ['__package__', '__file__']:
            if hasattr(module, attr) and getattr(module, attr):
                print('    {}: {}'.format(attr, getattr(module, attr)))

def silent_remove(filename):
    # Best effort delete; see: https://stackoverflow.com/a/10840586/509882
    try:
        os.remove(filename)
    except OSError as e:
        # errno.ENOENT = no such file or directory
        if e.errno != errno.ENOENT:
            # re-raise exception if a different error occurred
            raise

class TestMigrationSchemaModule(unittest.TestCase):

    def setUp(self):
        print()
        self.fixtures_path = fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'migrate')
        self.existing_defs_path = os.path.join(fixtures_path, 'small_existing.py')
        self.tmp_dir = mkdtemp()
        # make tmp dir in 'fixtures/migrate/tmp' so it can be accessed from Docker container's host
        self.tmp_model_dir = mkdtemp(dir=os.path.join(self.fixtures_path, 'tmp'))
        self.test_package = os.path.join(fixtures_path, 'test_package')
        self.test_module = os.path.join(self.test_package, 'test_module.py')
        ######## TODO FIX: these won't work on circle
        self.wc_dev_repos = wc_dev_repos = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self.current_wc_lang_core = os.path.join(wc_dev_repos, 'wc_lang', 'wc_lang', 'core.py')
        self.old_wc_lang_core = os.path.join(wc_dev_repos, 'old_wc_lang_19468f', 'wc_lang', 'core.py')

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        shutil.rmtree(self.tmp_model_dir)

    def get_module_name(self, pathname):
        return os.path.basename(pathname).split('.')[0]

    def test_parse_module_path(self):
        # exceptions
        not_a_python_file = os.path.join(self.tmp_dir, 'not_a_python_file.x')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a Python source file name"):
            MigrationSchemaModule.parse_module_path(not_a_python_file)
        no_such_file = os.path.join(self.tmp_dir, 'no_such_file.py')
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            MigrationSchemaModule.parse_module_path(no_such_file)
        not_a_file = mkdtemp(suffix='.py', dir=self.tmp_dir)
        with self.assertRaisesRegex(MigratorError, "'.+' is not a file"):
            MigrationSchemaModule.parse_module_path(not_a_file)

        # module that's not in a package
        expected_dir = None
        expected_package = None
        expected_module = self.get_module_name(self.existing_defs_path)
        self.assertEqual(MigrationSchemaModule.parse_module_path(self.existing_defs_path),
            (expected_dir, expected_package, expected_module))

        # module in package
        expected_dir = self.fixtures_path
        expected_package = 'test_package'
        expected_module = self.get_module_name(self.test_module)
        self.assertEqual(MigrationSchemaModule.parse_module_path(self.test_module),
            (expected_dir, expected_package, expected_module))

        # test at /; if files cannot be written to / these tests fail silently
        # module in /
        expected_module = self.get_module_name(self.existing_defs_path)
        module_in_root = os.path.join('/', os.path.basename(self.existing_defs_path))
        try:
            shutil.copy(self.existing_defs_path, module_in_root)
            expected_dir = None
            expected_package = None
            self.assertEqual(MigrationSchemaModule.parse_module_path(module_in_root),
                (expected_dir, expected_package, expected_module))
        except: 
            pass
        finally:
            # remove module_in_root if it exists
            silent_remove(module_in_root)
            
        # package whose root is /
        module_in_pkg_in_root = os.path.join('/', 'tmp', os.path.basename(self.existing_defs_path))
        try:
            src_dst_copy_pairs = [
                (os.path.join(self.test_package, '__init__.py'), '/'),
                (os.path.join(self.test_package, '__init__.py'), '/tmp/'),
                (self.existing_defs_path, '/tmp')
            ]
            for src, dst in src_dst_copy_pairs:
                shutil.copy(src, dst)
            expected_dir = '/'
            expected_package = 'tmp'
            self.assertEqual(MigrationSchemaModule.parse_module_path(module_in_pkg_in_root),
                (expected_dir, expected_package, expected_module))
        except: 
            pass
        finally:
            silent_remove('/__init__.py')

    @staticmethod
    def get_models(module):
        return [attr for _, attr in inspect.getmembers(module, inspect.isclass)
            if isinstance(attr, obj_model.core.ModelMeta)]

    @staticmethod
    def get_model_names(module):
        return set([name for name, attr in inspect.getmembers(module, inspect.isclass)
            if isinstance(attr, obj_model.core.ModelMeta)])

    def test_import_module_for_migration(self):
        # import module not in package
        msm = MigrationSchemaModule(self.existing_defs_path)
        module = msm.import_module_for_migration()
        self.assertIn(msm.module_path, MigrationSchemaModule.MODULES)
        self.assertEquals(module, MigrationSchemaModule.MODULES[msm.module_path])
        self.assertEquals(self.get_model_names(module),
            {'Test', 'DeletedModel', 'Property', 'Subtest', 'Reference'})
        # importing self.existing_defs_path again returns same module from cache
        self.assertEquals(module, msm.import_module_for_migration())

        # import module in a package
        msm = MigrationSchemaModule(self.test_module)
        module = msm.import_module_for_migration()
        self.assertEquals(self.get_model_names(module), {'Test', 'Reference', 'Foo'})

        # put the package's dir on sys.path, and import it again
        MigrationSchemaModule.MODULES = {}
        sys.path.append(self.fixtures_path)
        module = msm.import_module_for_migration()
        self.assertEquals(self.get_model_names(module), {'Test', 'Reference', 'Foo'})

        # import a module with a syntax bug
        bad_module = os.path.join(self.tmp_dir, 'bad_module.py')
        f = open(bad_module, "w")
        f.write('bad python')
        f.close()
        msm = MigrationSchemaModule(bad_module)
        with self.assertRaisesRegex(MigratorError, "cannot be imported and exec'ed"):
            msm.import_module_for_migration()

        # import current wc_lang
        msm = MigrationSchemaModule(self.current_wc_lang_core)
        module = msm.import_module_for_migration()
        # todo: stronger test
        self.assertTrue({'Taxon', 'Model'} < self.get_model_names(module))
        module = msm.import_module_for_migration()
        self.assertTrue({'Taxon', 'Model'} < self.get_model_names(module))
        
        # import old wc_lang
        msm = MigrationSchemaModule(self.old_wc_lang_core)
        # module = msm.import_module_for_migration(module_name='old_wc_lang_core')
        # module = msm.import_module_for_migration()
        # todo: stronger test
        self.assertTrue({'Taxon', 'Model'} < self.get_model_names(module))
        
