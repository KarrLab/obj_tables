'''
important import facts:
    import statements are absolute or relative
    absolute imports are resolved by directories in sys.path
    relative imports are relative to the module making the import

assumptions:
    using Python 3.5 or newer
    a schema is contained in one module
    the module may be in a package
    all obj_model.Models defined by the schema are declared as classes that are attributes of the module
        (that is, they're not, for example, subclasses of other classes)
    both schemas used in a migration may have the same default filename, module name and package name
    schemas do not do relative imports
    the directory containing the module contains a requirements.txt file for the package
    importing the schema does not have side-effects beyond modifying sys.modules

mechanism:::TestMigrationSchemaModule::test_parse_module_path
    use the 'import a Python source file directly' strategy in the importlib documentation
    if the schema module is in a package, add the package's path to sys.path before importing the schema
        because the module and other models it indirectly imports may make
        absolute imports which assume the package's path is in sys.path
    save loaded schemas in a dictionary and use it to avoid reloading a schema
    after importing a schema restore sys.modules so that a subsequent import of a different version
        of the schema's package does not use incompatible modules in the package
    if importing a schema fails, advise that schemas must be in a package that properly contains __init__.py files
        (in all directories from the schema up to the directory containing the package, and not above)

limitations:
    requirements
    obj_model versions

production plan:
    avoid side-effects and problems caused by reimporting similar packages
        by restoring sys.path and sys.modules after importlib.import_module()
    remove __pycache__ dirs before running importlib.import_module()
    perhaps provide means for separately configuring package_directory, package_name, and module_name
    backup plan: have people doing migration provide pyc files for schema; e.g., would be necessary if
        old schema requires on earlier versions of PyPI than installed
'''

# todo:
# schema provide requirements.txt file
# define parent package to do relative imports and avoid 'attempted relative import with no known
# parent package' error

import sys
import importlib
import importlib.util
from pathlib import Path

import obj_model


class MigratorError(Exception):
    """ Exception raised for errors in obj_model.migrate
    """
    def __init__(self, message=None):
        super().__init__(message)

class MigrationSchemaModule(object):
    """ Represent a schema module

    Attributes:
        module_path (:obj:`str`): path to the module
        package_directory (:obj:`str`): if the module is in a package, the path to the package's directory;
            otherwise `None`
        package_name (:obj:`str`): if the module is in a package, the name of the package containing the
            module; otherwise `None`
        module_name (:obj:`str`): the module's module name
    """

    # cached schema modules that have been imported, indexed by full pathnames
    MODULES = {}

    def __init__(self, module_path):
        self.module_path = module_path
        self.package_directory, self.package_name, self.module_name = self.parse_module_path(module_path)

    @staticmethod
    def parse_module_path(module_path):
        """ Convert the path to a module into its package directory, package name, and module name

        Package directory and package name are `None` if the module is not in a package

        Args:
            module_path (:obj:`str`): path of a Python module file

        Returns:
            :obj:`tuple`: the module path's package directory, package name, and module name

        Raises:
            :obj:`MigratorError`: if `module_path` is not the name of a Python file, or is not a file
        """
        path = Path(module_path).resolve()

        if not path.suffixes == ['.py']:
            raise MigratorError("'{}' is not a Python source file name".format(module_path))
        if not path.is_file():
            raise MigratorError("'{}' is not a file".format(module_path))

        # get highest directory that does not contain '__init__.py'
        dir = path.parent
        found_package = False
        while True:
            if not dir.joinpath('__init__.py').is_file():
                break
            # exit at / root
            if dir == dir.parent:
                break
            found_package = True
            dir = dir.parent
        package_directory, package_name = None, None
        if found_package:
            package_directory = str(dir)
            # obtain package name between directory and module
            package_name = str(path.relative_to(package_directory).parent).replace('/', '.')

        # obtain module name
        module_name = path.stem

        return package_directory, package_name, module_name

    def get_path(self):
        return str(self.module_path)

    def import_module_for_migration(self, module_name=None):
        """ Import a schema in a Python module

        Args:
            module_name (:obj:`str`, optional): name to use for the module being loaded; to avoid 
            'cannot use the same related attribute name' error in validate_related_attributes()
            use different values for module_name for different versions of a schema

        Returns:
            :obj:`Module`: the `Module` loaded from `self.module_path`

        Raises:
            :obj:`MigratorError`: if `self.module_path` cannot be loaded
        """
        if self.get_path() in self.MODULES:
            return self.MODULES[self.get_path()]

        # copy sys.paths and sys.modules so they can be restored and analyzed
        sys_attrs = ['path', 'modules']
        saved = {}
        for sys_attr in sys_attrs:
            saved[sys_attr] = getattr(sys, sys_attr).copy()

        # insert package directory at front of path so existing packages do not conflict
        if self.package_directory:
            if self.package_directory not in sys.path:
                sys.path.insert(0, self.package_directory)

        if module_name is None:
            module_name = self.module_name
        try:
            # note: unclear whether self.module_name here matters
            spec = importlib.util.spec_from_file_location(module_name, self.get_path())
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.MODULES[self.get_path()] = module
        except (SyntaxError, ImportError, AttributeError, ValueError) as e:
            raise MigratorError("'{}' cannot be imported and exec'ed: {}".format(self.get_path(), e))

        # restore sys.path
        sys.path = saved['path']
        # since exec_module may have changed the values of pre-existing entries in sys.modules
        # restore sys.modules by deleting those that are not new
        for name in list(sys.modules):
            if name not in saved['modules']:
                del sys.modules[name]

        return module

    def __str__(self):
        vals = []
        for attr in ['module_path', 'package_directory', 'package_name', 'module_name']:
            vals.append("{}: {}".format(attr, getattr(self, attr)))
        return '\n'.join(vals)

