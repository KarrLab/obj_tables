""" Utilities

:Author: Jonathan Karr <karr@mssm.edu>
:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2016-11-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from datetime import datetime
from itertools import chain
from pathlib import Path
from random import shuffle
from obj_tables.core import (Model, Attribute, StringAttribute, RelatedAttribute,  # noqa: F401
                             OneToOneAttribute, OneToManyAttribute, ManyToOneAttribute, ManyToManyAttribute,
                             InvalidObjectSet, Validator, TableFormat,
                             SCHEMA_TABLE_TYPE, SCHEMA_SHEET_NAME)
import collections
import importlib
import networkx
import obj_tables.io
import os.path
import pandas  # noqa: F401
import pkgutil
import random
import re
import string
import stringcase
import types
import wc_utils.workbook.io


def get_schema(path, name=None):
    """ Get a Python schema

    Args:
        path (:obj:`str`): path to Python schema
        name (:obj:`str`, optional): Python name for schema module

    Returns:
        :obj:`types.ModuleType`: schema
    """
    name = name or rand_schema_name()
    loader = importlib.machinery.SourceFileLoader(name, path)
    schema = loader.load_module()
    return schema


def rand_schema_name(len=8):
    """ Generate a random Python module name of a schema

    Args:
        len (:obj:`int`, optional): length of random name

    Returns:
        :obj:`str`: random name for schema
    """
    return 'schema_' + ''.join(random.choice(string.ascii_lowercase) for i in range(len))


def get_models(module):
    """ Get the models in a module

    Args:
        module (:obj:`types.ModuleType`): module

    Returns:
        :obj:`dict` of :obj:`str` => :obj:`Model`: dictionary that maps the names of models to models
    """
    models = {}
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, Model):
            models[attr_name] = attr
    return models


def get_related_models(root_model, include_root_model=False):
    """ Get the models that have relationships to a model

    Args:
        root_model (:obj:`type`): subclass of :obj:`Model`
        include_root_model (:obj:`bool`, optional): include the root model in the returned list of models

    Returns:
        :obj:`list` of :obj:`type`: list of models that have relationships with :obj:`root_model`
    """
    related_models = [root_model]
    to_check = [root_model]
    while to_check:
        cur_model = to_check.pop()

        for attr in cur_model.Meta.attributes.values():
            if isinstance(attr, RelatedAttribute) and attr.related_class not in related_models:
                related_models.append(attr.related_class)
                to_check.append(attr.related_class)

        for attr in cur_model.Meta.related_attributes.values():
            if attr.primary_class not in related_models:
                related_models.append(attr.primary_class)
                to_check.append(attr.primary_class)

    if not include_root_model:
        related_models.pop(0)

    return related_models


def get_attribute_by_name(cls, group_name, attr_name, verbose_name=False, case_insensitive=False):
    """ Return the attribute of `Model` class `cls` with name `name`

    Args:
        cls (:obj:`class`): Model class
        group_name (:obj:`str`): name of attribute group
        attr_name (:obj:`str`): attribute name
        verbose_name (:obj:`str`): if :obj:`True`, search for attributes by verbose name; otherwise search for attributes by name
        case_insensitive (:obj:`bool`, optional): if True, ignore case

    Returns:
        :obj:`Attribute`: attribute with name equal to the value of `group_name` or `None` if there is no matching attribute
        :obj:`Attribute`: attribute with name equal to the value of `attr_name` or `None` if there is no matching attribute
    """

    if not attr_name:
        return (None, None)

    attr_order = list(cls.Meta.attribute_order)
    attr_order.extend(list(set(cls.Meta.attributes.keys()).difference(set(attr_order))))

    for attr_name_to_search in attr_order:
        attr = cls.Meta.attributes[attr_name_to_search]
        if group_name is None:
            if (not case_insensitive and ((not verbose_name and attr.name == attr_name) or
                                          (verbose_name and attr.verbose_name == attr_name))) or \
                (case_insensitive and ((not verbose_name and attr.name.lower() == attr_name.lower()) or
                                       (verbose_name and attr.verbose_name.lower() == attr_name.lower()))):
                return (None, attr)
        else:
            if isinstance(attr, RelatedAttribute) and attr.related_class.Meta.table_format == TableFormat.multiple_cells:
                if attr.name.lower() == group_name.lower() or attr.verbose_name.lower() == group_name.lower():
                    sub_attr = get_attribute_by_name(attr.related_class, None, attr_name, verbose_name=verbose_name,
                                                     case_insensitive=case_insensitive)
                    return (attr, sub_attr[1])

    return (None, None)


def group_objects_by_model(objects):
    """ Group objects by their models

    Args:
        objects (:obj:`list` of :obj:`Model`): list of model objects

    Returns:
        :obj:`dict`: dictionary with object grouped by their class
    """
    grouped_objects = {}
    for obj in objects:
        if obj.__class__ not in grouped_objects:
            grouped_objects[obj.__class__] = []
        if obj not in grouped_objects[obj.__class__]:
            grouped_objects[obj.__class__].append(obj)
    return grouped_objects


def get_related_errors(object):
    """ Get all errors associated with an object and its related objects

    Args:
        object (:obj:`Model`): object

    Returns:
        :obj:`InvalidObjectSet`: set of errors
    """
    objects = object.get_related()
    if object not in objects:
        objects.append(object)
    return Validator().run(objects)


def get_component_by_id(models, id, identifier='id'):
    ''' Retrieve a model instance by its identifier

    Args:
        model (:obj:list of `Model`): an iterable of `Model` objects
        id (:obj:`str`): the identifier being sought
        identifier (:obj:`str`, optional): the name of the identifier attribute

    Returns:
        :obj:`Model`: the retrieved Model instance if found, or None

    Raises:
        :obj:`AttributeError`: if `model` does not have the attribute specified by `identifier`
    '''
    # TODO: this is O(n); achieve O(1) by using Manager() dictionaries id -> component for each model
    for model in models:
        try:
            if getattr(model, identifier) == id:
                return model
        except AttributeError:
            raise AttributeError("{} does not have the attribute '{}'".format(model.__class__.__name__,
                                                                              identifier))
    return None


def randomize_object_graph(obj):
    """ Randomize the order of the edges (RelatedManagers) in the object's object graph.

    Args:
        obj (:obj:`Model`): instance of :obj:`Model`
    """
    randomized_objs = []
    objs_to_randomize = [obj]

    while objs_to_randomize:
        obj = objs_to_randomize.pop()
        if obj not in randomized_objs:
            randomized_objs.append(obj)

            for attr_name, attr in chain(obj.Meta.attributes.items(), obj.Meta.related_attributes.items()):
                if isinstance(attr, RelatedAttribute):
                    val = getattr(obj, attr_name)
                    if isinstance(val, list) and len(val) > 1:
                        # randomize children
                        objs_to_randomize.extend(val)

                        # shuffle related manager
                        shuffle(val)


def source_report(obj, attr_name):
    """ Get the source file, worksheet, column, and row location of attribute `attr_name` of
    model object `obj` as a colon-separated string.

    Args:
        obj (:obj:`Model`): model object
        attr_name (:obj:`str`): attribute name

    Returns:
        :obj:`str`: a string representation of the source file, worksheet, column, and row
            location of `attr_name` of `obj`
    """
    ext, filename, worksheet, row, column = obj.get_source(attr_name)
    if 'xlsx' in ext:
        return "{}:{}:{}{}".format(filename, worksheet, column, row)
    else:
        return "{}:{}:{},{}".format(filename, worksheet, row, column)


def set_git_repo_metadata_from_path(model, repo_type, path='.', url_attr='url', branch_attr='branch',
                                    commit_hash_attr='revision'):
    """ Use Git to set the Git repository URL, branch, and commit hash metadata attributes of a model

    Args:
        model (:obj:`Model`): model whose Git attributes will be set
        repo_type (:obj:`git.RepoMetadataCollectionType`): repo type being set
        path (:obj:`str`, optional): path to file or directory in a clone of a Git repository; default='.'
        url_attr (:obj:`str`, optional): attribute in `model` for the Git URL; default='url'
        branch_attr (:obj:`str`, optional): attribute in `model` for the Git branch; default='branch'
        commit_hash_attr (:obj:`str`, optional): attribute in `model` for the Git commit hash;
            default='revision'

    Returns:
        :obj:`list` of :obj:`str`: list of reasons, if any, that the repo might not be
            suitable for collecting metadata
    """
    from wc_utils.util import git

    md, unsuitable_changes = git.get_repo_metadata(path=path, repo_type=repo_type, data_file=path)
    setattr(model, url_attr, md.url)
    setattr(model, branch_attr, md.branch)
    setattr(model, commit_hash_attr, md.revision)
    return unsuitable_changes


# Git repository metadata from an `obj_tables` data file
DataFileMetadata = collections.namedtuple('DataFileMetadata', 'data_repo_metadata, schema_repo_metadata')
DataFileMetadata.__doc__ += ': Git repository metadata from an obj_tables data file'
DataFileMetadata.data_repo_metadata.__doc__ = "Git metadata about the repository containing the file"
DataFileMetadata.schema_repo_metadata.__doc__ = \
    "Git metadata about the repository containing the obj_tables schema used by the file"


def read_metadata_from_file(pathname):
    """ Read Git repository metadata from an `obj_tables` data file

    Args:
        pathname (:obj:`str`): path to the data file

    Returns:
        :obj:`DataFileMetadata`: data and schema repo metadata from the file at `pathname`; missing
        metadata is returned as :obj:`None`

    Raises:
        :obj:`ValueError`: if `pathname`'s extension is not supported,
            or unexpected metadata instances are found
    """
    reader = obj_tables.io.Reader.get_reader(pathname)

    metadata_instances = reader().run(pathname, models=[DataRepoMetadata, SchemaRepoMetadata],
                                      allow_multiple_sheets_per_model=True,
                                      ignore_extra_models=True, ignore_missing_models=True,
                                      group_objects_by_model=True, ignore_attribute_order=True)
    metadata_class_to_attr = {
        DataRepoMetadata: 'data_repo_metadata',
        SchemaRepoMetadata: 'schema_repo_metadata'
    }
    data_file_metadata_dict = {
        'data_repo_metadata': None,
        'schema_repo_metadata': None
    }
    for model_class, instances in metadata_instances.items():
        if len(instances) == 1:
            data_file_metadata_dict[metadata_class_to_attr[model_class]] = instances[0]
        elif 1 < len(instances):
            raise ValueError("Multiple instances of {} found in '{}'".format(model_class.__name__,
                                                                             pathname))
    return DataFileMetadata(**data_file_metadata_dict)


# todo: make this more convenient by eliminating models. either a) change schema_package to the path
# to the schema and use the modules in it, or b) use wc_utils.workbook.io to copy all data in
# the existing file and using WriterBase.make_metadata_objects() to obtain the metadata
# todo: make a CLI command for add_metadata_to_file -- it will need to use IO classes like migrate.py
def add_metadata_to_file(pathname, models, schema_package=None):
    """ Add Git repository metadata to an existing `obj_tables` data file

    Overwrites the existing file

    Args:
        pathname (:obj:`str`): path to an `obj_tables` data file in a Git repo
        models (:obj:`list` of :obj:`types.TypeType`, optional): list of types of objects to read
        schema_package (:obj:`str`, optional): the package which defines the `obj_tables` schema
            used by the file; if not :obj:`None`, try to write metadata information about the
            the schema's Git repository: the repo must be current with origin

    Returns:
        :obj:`str`: pathname of new data file

    Raises:
        :obj:`ValueError`: if `overwrite` is not set the new file would overwrite an existing file
    """
    # read file
    path = Path(pathname).resolve()
    objects = obj_tables.io.Reader().run(str(path), models=models, group_objects_by_model=False)
    # write file with metadata
    obj_tables.io.Writer().run(str(path), objects, models=models, data_repo_metadata=True,
                               schema_package=schema_package)
    return path


class RepoMetadata(Model):
    """ Generic Model to store Git version information about a repo """
    url = StringAttribute()
    branch = StringAttribute()
    revision = StringAttribute()

    class Meta(Model.Meta):
        table_format = TableFormat.column
        attribute_order = ('url', 'branch', 'revision')


class DataRepoMetadata(RepoMetadata):
    """ Model to store Git version information about a data file's repo """
    pass


class SchemaRepoMetadata(RepoMetadata):
    """ Model to store Git version info for the repo that defines the obj_tables schema used by a data file """
    pass


def get_attrs():
    """ Get a dictionary of the defined types of attributes for use with :obj:`init_schema`.

    Returns:
        :obj:`dict`: dictionary which maps the name of each attribute to its instance
    """
    modules_to_explore = [obj_tables]
    attrs = set()
    attr_names = {}

    while modules_to_explore:
        module = modules_to_explore.pop()
        if hasattr(module, '__path__'):
            submodule_infos = pkgutil.iter_modules(module.__path__)
            modules_to_explore.extend(importlib.import_module(module.__name__ + '.' + module_info.name) for module_info in submodule_infos)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Attribute) and \
                    attr != Attribute and \
                    attr not in attrs:
                assert attr_name.endswith('Attribute')
                attrs.add(attr)
                short_attr_name, _, _ = attr_name.rpartition('Attribute')
                attr_full_name = (module.__name__ + '.' + short_attr_name).replace(obj_tables.__name__ + '.', '')
                attr_names[attr_full_name] = attr

    return attr_names


def init_schema(filename, out_filename=None):
    """ Initialize an `obj_tables` schema from a tabular declarative specification in
    :obj:`filename`. :obj:`filename` can be a Excel, CSV, or TSV file.

    Schemas (classes and attributes) should be defined using the following tabular format.
    Classes and their attributes can be defined in any order.

    .. table:: Format for specifying classes.
        :name: class_tabular_schema

        =====================================  =========================  =========================================  ========
        Python                                 Tabular column             Tabular column values                      Optional
        =====================================  =========================  =========================================  ========
        Class name                             !Name                      Valid Python name
        Class                                  !Type                      `Class`
        Superclass                             !Parent                    Empty or the name of another class
        `obj_tables.Meta.table_format`         !Format                    `row`, `column`, `multiple_cells`, `cell`
        `obj_tables.Meta.verbose_name`         !Verbose name              String                                     Y
        `obj_tables.Meta.verbose_name_plural`  !Verbose name plural       String                                     Y
        `obj_tables.Meta.description`          !Description                                                          Y
        =====================================  =========================  =========================================  ========

    .. table:: Format for specifying attributes of classes.
        :name: attribute_tabular_schema

        ======================================================  ====================  ==========================================  ========
        Python                                                  Tabular column        Tabular column values                       Optional
        ======================================================  ====================  ==========================================  ========
        Name of instance of subclass of `obj_tables.Attribute`  !Name                 a-z, A-Z, 0-9, _, :, >, ., -, [, ], or ' '
        `obj_tables.Attribute`                                  !Type                 `Attribute`
        Parent class                                            !Parent               Name of the parent class
        Subclass of `obj_tables.Attribute`                      !Format               `Boolean`, `Float`, `String`, etc.
        `obj_tables.Attribute.verbose_name`                     !Verbose name         String                                      Y
        `obj_tables.Attribute.verbose_name_plural`              !Verbose name plural  String                                      Y
        `obj_tables.Attribute.description`                      !Description          String                                      Y
        ======================================================  ====================  ==========================================  ========

    Args:
        filename (:obj:`str`): path to
        out_filename (:obj:`str`, optional): path to save schema

    Returns:
        :obj:`types.ModuleType`: module with classes
        :obj:`str`: schema name

    Raises:
        :obj:`ValueError`: if schema specification is not in a supported format,
            an Excel schema file does not contain a worksheet with the name `!!_Schema` which specifies the schema,
            the class inheritance structure is cyclic,
            or the schema specification is invalid (e.g., a class is defined multiple defined)
    """
    from obj_tables.io import WorkbookReader

    base, ext = os.path.splitext(filename)
    if ext in ['.xlsx']:
        sheet_name = '!!' + SCHEMA_SHEET_NAME
    elif ext in ['.csv', '.tsv']:
        if '*' in filename:
            sheet_name = '!!' + SCHEMA_SHEET_NAME
        else:
            sheet_name = ''
    else:
        raise ValueError('{} format is not supported.'.format(ext))

    wb = wc_utils.workbook.io.read(filename)
    if sheet_name not in wb:
        raise ValueError('File must contain a sheet with name "{}".'.format(
            sheet_name))
    ws = wb[sheet_name]

    name_col_name = '!Name'
    type_col_name = '!Type'
    parent_col_name = '!Parent'
    format_col_name = '!Format'
    verbose_name_col_name = '!Verbose name'
    verbose_name_plural_col_name = '!Verbose name plural'
    desc_col_name = '!Description'

    class_type = 'Class'
    attr_type = 'Attribute'

    rows = ws
    doc_metadata, model_metadata, _ = WorkbookReader.read_worksheet_metadata(sheet_name, rows)

    doc_schema_name = doc_metadata.get('schema', None)
    schema_schema_name = model_metadata.get('name', None)
    assert not doc_schema_name or not schema_schema_name or doc_schema_name == schema_schema_name, \
        "Schema names must be None or equal"
    schema_name = doc_schema_name or schema_schema_name
    module_name = schema_name or rand_schema_name()

    if model_metadata.get('type', None) != SCHEMA_TABLE_TYPE:
        raise ValueError("Type must be '{}'.".format(SCHEMA_TABLE_TYPE))

    # parse model specifications
    header_row = rows[0]
    rows = rows[1:]

    cls_specs = {}
    for row_list in rows:
        # ignore empty rows
        if all(cell in [None, ''] for cell in row_list):
            continue

        row = {}
        for header, cell in zip(header_row, row_list):
            row[header] = cell

        if row[type_col_name] == class_type:
            cls_name = row[name_col_name]
            if cls_name in cls_specs:
                cls = cls_specs[cls_name]
                if cls['explictly_defined']:
                    raise ValueError('Class "{}" can only be defined once.'.format(
                        cls_name))
                cls['explictly_defined'] = True
            else:
                cls = cls_specs[cls_name] = {
                    'super_class': None,
                    'name': cls_name,
                    'attrs': {},
                    'attr_order': [],
                    'explictly_defined': True,
                }
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', cls_name):
                    raise ValueError(("Invalid class name '{}'. "
                                      "Class names must start with a letter or underscore, "
                                      "and consist of letters, numbers, and underscores.").format(
                        cls_name))

            if row[parent_col_name]:
                cls['super_class'] = row[parent_col_name]

            def_verbose_name = cls_name

            cls['tab_format'] = TableFormat[row[format_col_name] or 'row']
            cls['verbose_name'] = row.get(verbose_name_col_name, def_verbose_name) or def_verbose_name
            cls['verbose_name_plural'] = row.get(verbose_name_plural_col_name, def_verbose_name) or def_verbose_name
            cls['desc'] = row.get(desc_col_name, None) or None

        elif row[type_col_name] == attr_type:
            cls_name = row[parent_col_name]
            if cls_name in cls_specs:
                cls = cls_specs[cls_name]
            else:
                cls = cls_specs[cls_name] = {
                    'explictly_defined': False,
                    'super_class': None,
                    'name': cls_name,
                    'attrs': {},
                    'attr_order': [],
                    'tab_format': TableFormat.row,
                    'verbose_name': cls_name,
                    'verbose_name_plural': cls_name,
                    'desc': None,
                }
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', cls_name):
                    raise ValueError(("Invalid class name '{}'. "
                                      "Class names must start with a letter or underscore, "
                                      "and consist of letters, numbers, and underscores.").format(
                        cls_name))

            attr_name = row[name_col_name]
            if not re.match(r'^[a-zA-Z0-9_:>\.\- \[\]]+$', attr_name):
                raise ValueError(("Invalid attribute name '{}'. "
                                  "Attribute names must consist of alphanumeric "
                                  "characters, underscores, colons, forward carets, "
                                  "dots, dashes, square brackets, and spaces.").format(
                    attr_name))
            attr_name = re.sub(r'[^a-zA-Z0-9_]', '_', attr_name)
            attr_name = stringcase.snakecase(attr_name)
            attr_name = re.sub(r'_+', '_', attr_name)

            if attr_name == 'Meta':
                raise ValueError('"{}" cannot have attribute with name "Meta".'.format(
                    cls_name))  # pragma: no cover # unreachable because snake case is all lowercase
            if attr_name in cls['attrs']:
                raise ValueError('Attribute "{}" of "{}" can only be defined once.'.format(
                    row[name_col_name], cls_name))

            cls['attrs'][attr_name] = {
                'name': attr_name,
                'type': row[format_col_name],
                'desc': row.get(desc_col_name, None),
                'verbose_name': row.get(verbose_name_col_name, row[name_col_name])
            }
            cls['attr_order'].append(attr_name)

        else:
            raise ValueError('Type "{}" is not supported.'.format(row[type_col_name]))

    # check that the inheritance graph is valid (i.e. acyclic)
    inheritance_graph = networkx.DiGraph()
    sub_classes = {'obj_tables.Model': []}
    for cls_name, cls_spec in cls_specs.items():
        if cls_spec['super_class']:
            inheritance_graph.add_edge(cls_spec['super_class'], cls_name)
            if cls_spec['super_class'] not in sub_classes:
                sub_classes[cls_spec['super_class']] = []
            sub_classes[cls_spec['super_class']].append(cls_name)
        else:
            inheritance_graph.add_edge('obj_tables.Model', cls_name)
            sub_classes['obj_tables.Model'].append(cls_name)
    if list(networkx.simple_cycles(inheritance_graph)):
        raise ValueError('The model inheritance graph must be acyclic.')

    # create classes
    module = type(module_name, (types.ModuleType, ), {})

    all_attrs = get_attrs()
    classes_to_construct = list(sub_classes['obj_tables.Model'])
    while classes_to_construct:
        cls_name = classes_to_construct.pop()
        cls_spec = cls_specs[cls_name]
        classes_to_construct.extend(sub_classes.get(cls_name, []))

        meta_attrs = {
            'table_format': cls_spec['tab_format'],
            'attribute_order': tuple(cls_spec['attr_order']),
            'description': cls_spec['desc'],
        }
        if cls_spec['verbose_name']:
            meta_attrs['verbose_name'] = cls_spec['verbose_name']
        if cls_spec['verbose_name_plural']:
            meta_attrs['verbose_name_plural'] = cls_spec['verbose_name_plural']

        attrs = {
            '__module__': module_name,
            '__doc__': cls_spec['desc'],
            'Meta': type('Meta', (Model.Meta, ), meta_attrs),
        }
        for attr_spec in cls_spec['attrs'].values():
            attr_type_spec, _, args = attr_spec['type'].partition('(')
            attr_type = all_attrs[attr_type_spec]
            attr_spec['python_type'] = attr_type_spec + 'Attribute'
            if args:
                attr_spec['python_args'] = args[0:-1]
                if attr_spec['verbose_name']:
                    attr_spec['python_args'] += ", verbose_name='{}'".format(attr_spec['verbose_name'])
            else:
                attr_spec['python_args'] = ''
                if attr_spec['verbose_name']:
                    attr_spec['python_args'] = "verbose_name='{}'".format(attr_spec['verbose_name'])

            if args:
                attr = eval('func(' + args, {}, {'func': attr_type})
            else:
                attr = attr_type()
            attr.verbose_name = attr_spec['verbose_name']
            attr.description = attr_spec['desc']
            attrs[attr_spec['name']] = attr

        if cls_spec['super_class'] is None or cls_spec['super_class'] == 'obj_tables.Model':
            super_class = Model
        else:
            super_class = getattr(module, cls_spec['super_class'])

        cls = type(cls_spec['name'], (super_class, ), attrs)
        setattr(module, cls_spec['name'], cls)

    # optionally, generate a Python file
    if out_filename:
        with open(out_filename, 'w') as file:
            # print documentation
            file.write('# Schema automatically generated at {:%Y-%m-%d %H:%M:%S}\n\n'.format(
                datetime.now()))

            # print import statements
            imported_modules = set(['obj_tables'])
            for cls_spec in cls_specs.values():
                for attr_spec in cls_spec['attrs'].values():
                    imported_modules.add('obj_tables.' + attr_spec['python_type'].rpartition('.')[0])
            if 'obj_tables.' in imported_modules:
                imported_modules.remove('obj_tables.')
            for imported_module in imported_modules:
                file.write('import {}\n'.format(imported_module))

            # print definition of * import behavior
            file.write('\n')
            file.write('\n')
            file.write('__all__ = [\n')
            file.write(''.join("    '{}',\n".format(cls_name) for cls_name in sorted(cls_specs.keys())))
            file.write(']\n')

            # print class definitions
            classes_to_define = list(sub_classes['obj_tables.Model'])
            while classes_to_define:
                cls_name = classes_to_define.pop()
                cls_spec = cls_specs[cls_name]
                classes_to_define.extend(sub_classes.get(cls_name, []))

                if cls_spec['super_class']:
                    super_class = cls_spec['super_class']
                else:
                    super_class = 'obj_tables.Model'

                file.write('\n')
                file.write('\n')
                file.write('class {}({}):\n'.format(cls_spec['name'], super_class))
                if cls_spec['desc']:
                    file.write('    """ {} """\n\n'.format(cls_spec['desc']))
                for attr_name in cls_spec['attr_order']:
                    attr_spec = cls_spec['attrs'][attr_name]
                    file.write('    {} = obj_tables.{}({})\n'.format(attr_spec['name'],
                                                                     attr_spec['python_type'],
                                                                     attr_spec['python_args']))

                file.write('\n')
                file.write('    class Meta(obj_tables.Model.Meta):\n')
                file.write("        table_format = obj_tables.TableFormat.{}\n".format(
                    cls_spec['tab_format'].name))
                file.write("        attribute_order = (\n{}        )\n".format(
                    "".join("            '{}',\n".format(attr) for attr in cls_spec['attr_order'])
                ))
                if cls_spec['verbose_name']:
                    file.write("        verbose_name = '{}'\n".format(
                        cls_spec['verbose_name'].replace("'", "\'")
                    ))
                if cls_spec['verbose_name_plural']:
                    file.write("        verbose_name_plural = '{}'\n".format(
                        cls_spec['verbose_name_plural'].replace("'", "\'")
                    ))
                if cls_spec['desc']:
                    file.write("        description = '{}'\n".format(cls_spec['desc'].replace("'", "\'")))

    # return the created module and its name
    return (module, schema_name)


def to_pandas(objs, models=None, get_related=True,
              include_all_attributes=True, validate=True):
    """ Generate a pandas representation of a collection of objects

    Args:
        objs (:obj:`list` of :obj:`Model`): objects
        models (:obj:`list` of :obj:`Model`, optional): models in the order that they should
            appear as worksheets; all models which are not in `models` will
            follow in alphabetical order
        get_related (:obj:`bool`, optional): if :obj:`True`, write `objects` and all their related objects
        include_all_attributes (:obj:`bool`, optional): if :obj:`True`, export all attributes including those
            not explictly included in `Model.Meta.attribute_order`
        validate (:obj:`bool`, optional): if :obj:`True`, validate the data

    Returns:
        :obj:`dict`: dictionary that maps models (:obj:`Model`) to
            the instances of each model (:obj:`pandas.DataFrame`)
    """
    from obj_tables.io import PandasWriter
    return PandasWriter().run(objs,
                              models=models,
                              get_related=get_related,
                              include_all_attributes=include_all_attributes,
                              validate=validate)


def diff_workbooks(filename_1, filename_2, models, model_name, schema_name=None, **kwargs):
    """ Get difference of models in two workbooks

    Args:
        filename_1 (:obj:`str`): path to first workbook
        filename_2 (:obj:`str`): path to second workbook
        models (:obj:`list` of :obj:`Model`): schema for objects to compare
        model_name (:obj:`str`): Type of objects to compare
        schema_name (:obj:`str`, optional): name of the schema
        kwargs (:obj:`dict`, optional): additional arguments to :obj:`obj_tables.io.Reader`

    Returns:
        :obj:`list` of :obj:`str`: list of differences
    """
    objs1 = obj_tables.io.Reader().run(filename_1,
                                       schema_name=schema_name,
                                       models=models,
                                       group_objects_by_model=True,
                                       **kwargs)
    objs2 = obj_tables.io.Reader().run(filename_2,
                                       schema_name=schema_name,
                                       models=models,
                                       group_objects_by_model=True,
                                       **kwargs)

    for model in models:
        if model.__name__ == model_name:
            break
    if model.__name__ != model_name:
        raise ValueError('Workbook does not have model "{}".'.format(model_name))

    obj_diffs = []
    for obj1 in list(objs1[model]):
        match = False
        for obj2 in list(objs2[model]):
            if obj1.serialize() == obj2.serialize():
                match = True
                objs2[model].remove(obj2)
                obj_diff = obj1.difference(obj2)
                if obj_diff:
                    obj_diffs.append(obj_diff)
                break
        if match:
            objs1[model].remove(obj1)

    diffs = []
    if objs1[model]:
        diffs.append('{} objects in the first workbook are missing from the second:\n  {}'.format(
            len(objs1[model]), '\n  '.join(obj.serialize() for obj in objs1[model])))
    if objs2[model]:
        diffs.append('{} objects in the second workbook are missing from the first:\n  {}'.format(
            len(objs2[model]), '\n  '.join(obj.serialize() for obj in objs2[model])))
    if obj_diffs:
        diffs.append('{} objects are different in the workbooks:\n  {}'.format(
            len(obj_diffs), '\n  '.join(obj_diffs)))

    return diffs


def viz_schema(module, filename):
    """ Visualize a schema

    Args:
        models (:obj:`types.ModuleType`): module with models
        filename (:obj:`str`): path to save visualization of schema
    """
    import graphviz

    models = get_models(module)
    dot = graphviz.Digraph(comment='Schema', graph_attr={'rankdir': 'LR'})

    for model in models.values():
        labels = [f'<TR><TD BGCOLOR="#FF8A5B" COLSPAN="2"><FONT POINT-SIZE="18"><B>{model.__name__}</B></FONT></TD></TR>']

        attr_names = get_attr_order(model)

        for i_attr, attr_name in enumerate(attr_names):
            attr = model.Meta.attributes[attr_name]

            if isinstance(attr, RelatedAttribute):
                related_model = attr.related_class
                i_related_attr = len(related_model.Meta.attributes) + \
                    sorted(related_model.Meta.related_attributes.keys()).index(attr.related_name)

                if isinstance(attr, OneToOneAttribute):
                    attr_type = related_model.__name__
                    headlabel = '1'
                    taillabel = '1'
                elif isinstance(attr, OneToManyAttribute):
                    attr_type = f'<I>list of </I> {related_model.__name__}'
                    headlabel = '1'
                    taillabel = 'N'
                elif isinstance(attr, ManyToOneAttribute):
                    attr_type = related_model.__name__
                    headlabel = 'N'
                    taillabel = '1'
                elif isinstance(attr, ManyToManyAttribute):
                    attr_type = f'<I>list of </I> {related_model.__name__}'
                    headlabel = 'N'
                    taillabel = 'N'

                dot.edge(f'{model.__name__}:{i_attr}',
                         f'{related_model.__name__}:{i_related_attr}',
                         headlabel=headlabel,
                         taillabel=taillabel)
            else:
                attr_type = attr.__class__.__name__.rpartition('Attribute')[0]

            i_row = i_attr
            if i_row % 2 == 1:
                bg = '#EBFFFF'
            else:
                bg = '#BFFFFF'
            labels.append(f'<TR><TD BGCOLOR="{bg}"><B>{attr_name}</B></TD><TD PORT="{i_row}" BGCOLOR="{bg}">{attr_type}</TD></TR>')

        for i_attr, attr_name in enumerate(sorted(model.Meta.related_attributes.keys())):
            attr = model.Meta.related_attributes[attr_name]
            if isinstance(attr, (OneToOneAttribute, OneToManyAttribute)):
                attr_type = attr.primary_class.__name__
            else:
                attr_type = f'<I>list of </I> {attr.primary_class.__name__}'
            i_row = i_attr + len(attr_names)
            if i_row % 2 == 1:
                bg = '#EBFFFF'
            else:
                bg = '#BFFFFF'
            labels.append(f'<TR><TD PORT="{i_row}" BGCOLOR="{bg}"><B>{attr_name}</B></TD><TD BGCOLOR="{bg}">{attr_type}</TD></TR>')

        dot.node(model.__name__,
                 label='<<TABLE CELLPADDING="4" CELLSPACING="0" BORDER="0" CELLBORDER="1">'
                 + ''.join(labels)
                 + '</TABLE>>',
                 shape="none", margin="0.0,0.055")

    root, ext = os.path.splitext(filename)
    dot.render(root, format=ext[1:], cleanup=True)


def get_attr_order(model):
    """ Get the names of attributes in the order they should appear in ER diagrams

    Args:
        model (:obj:`type`): model

    Returns:
        :obj:`list` of :obj:`str`: names of attributes in the order they should appear in ER diagrams
    """
    attrs = list(model.Meta.attribute_order)
    attrs += sorted(set(model.Meta.attributes.keys()) - set(attrs))
    return attrs
