""" Command line utilities for modeling data in tables (Excel, CSV, TSV)

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-11
:Copyright: 2019, Karr Lab
:License: MIT
"""

from . import core
from . import io
from . import utils
import cement
import obj_model
import os.path
import sys
import types


class BaseController(cement.Controller):
    """ Base controller for command line application """

    class Meta:
        label = 'base'
        description = "Command line utilities for modeling data in tables (Excel, CSV, TSV)"
        help = "Command line utilities for modeling data in tables (Excel, CSV, TSV)"
        arguments = [
            (['-v', '--version'], dict(action='version', version=obj_model.__version__)),
        ]

    @cement.ex(hide=True)
    def _default(self):
        self._parser.print_help()


class ConvertController(cement.Controller):
    """ Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML) """
    class Meta:
        label = 'convert'
        description = 'Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML)'
        help = 'Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML)'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or a declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['in_wb_file'], dict(type=str,
                                  help='Path to the workbook (.csv, .json, .tsv, .xlsx, .yml)')),
            (['out_wb_file'], dict(type=str,
                                   help='Path to save the workbook (.csv, .json, .tsv, .xlsx, .yml)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        _, models = get_schema_models(args.schema_file)
        objs = io.WorkbookReader().run(args.in_wb_file, models=models, group_objects_by_model=False)
        io.WorkbookWriter().run(args.out_wb_file, objs, models=models)
        print('Workbook saved to {}'.format(args.out_wb_file))


class DiffController(cement.Controller):
    """ Calculate the difference between two workbooks according to a schema """
    class Meta:
        label = 'diff'
        description = 'Calculate the difference between two workbooks according to a schema'
        help = 'Calculate the difference between two workbooks according to a schema'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or a declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['model'], dict(type=str,
                             help='Type of objects to compare')),
            (['wb_file_1'], dict(type=str,
                                 help='Path to the first workbook (.csv, .json, .tsv, .xlsx, .yml)')),
            (['wb_file_2'], dict(type=str,
                                 help='Path to the second workbook (.csv, .json, .tsv, .xlsx, .yml)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        _, models = get_schema_models(args.schema_file)
        objs1 = io.WorkbookReader().run(args.wb_file_1, models=models)
        objs2 = io.WorkbookReader().run(args.wb_file_2, models=models)

        for model in models:
            if model.__name__ == args.model:
                break
        if model.__name__ != args.model:
            raise SystemExit('Workbook does not have model "{}"'.format(args.model))

        diffs = []
        for obj1 in list(objs1[model]):
            match = False
            for obj2 in list(objs2[model]):
                if obj1.serialize() == obj2.serialize():
                    match = True
                    objs2[model].remove(obj2)
                    diff = obj1.difference(obj2)
                    if diff:
                        diffs.append(diff)
                    break
            if match:
                objs1[model].remove(obj1)

        errors = []
        if objs1[model]:
            errors.append('{} objects in the first workbook are missing from the second:\n  {}'.format(
                len(objs1[model]), '\n  '.join(obj.serialize() for obj in objs1[model])))
        if objs2[model]:
            errors.append('{} objects in the second workbook are missing from the first:\n  {}'.format(
                len(objs2[model]), '\n  '.join(obj.serialize() for obj in objs2[model])))
        if diffs:
            errors.append('{} objects are different in the workbooks:\n  {}'.format(
                len(diffs), '\n  '.join(diffs)))
        if errors:
            raise SystemExit('\n\n'.join(errors))

        if not objs1[model] and not objs2[model] and not diffs:
            print('Workbooks are equivalent')


class GenSchemaController(cement.Controller):
    """ Generate a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV) """
    class Meta:
        label = 'gen-schema'
        description = 'Generate a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
        help = 'Generate a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['in_file'], dict(type=str,
                               help='Path to the declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['out_file'], dict(type=str,
                                help='Path to save Python schema (.py)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        utils.gen_schema(args.in_file, out_filename=args.out_file)
        print('Schema saved to {}'.format(args.out_file))


class GenTemplateController(cement.Controller):
    """ Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema """
    class Meta:
        label = 'gen-template'
        description = 'Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema'
        help = 'Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['template_file'], dict(type=str,
                                     help='Path to save the template (.csv, .tsv, .xlsx)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        _, models = get_schema_models(args.schema_file)
        io.WorkbookWriter().run(args.template_file, [], models=models)
        print('Template saved to {}'.format(args.template_file))


class NormalizeController(cement.Controller):
    """ Normalize a workbook according to a schema """
    class Meta:
        label = 'normalize'
        description = 'Generate a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
        help = 'Generate a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or a declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['model'], dict(type=str,
                             help='Type of objects to normalize')),
            (['in_wb_file'], dict(type=str,
                                  help='Path to the workbook (.csv, .json, .tsv, .xlsx, .yml)')),
            (['out_wb_file'], dict(type=str,
                                   help='Path to save the normalized workbook (.csv, .json, .tsv, .xlsx, .yml)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        _, models = get_schema_models(args.schema_file)
        for model in models:
            if model.__name__ == args.model:
                break
        if model.__name__ != args.model:
            raise SystemExit('Workbook does not have model "{}"'.format(args.model))

        objs = io.WorkbookReader().run(args.in_wb_file, models=models, group_objects_by_model=False)
        for obj in objs:
            if isinstance(obj, model):
                obj.normalize()
        io.WorkbookWriter().run(args.out_wb_file, objs, models=models)
        print('Normalized workbook saved to {}'.format(args.out_wb_file))


class ValidateController(cement.Controller):
    """ Validate that a workbook is consistent with a schema, and report any errors """
    class Meta:
        label = 'validate'
        description = 'Validate that a workbook is consistent with a schema, and report any errors'
        help = 'Validate that a workbook is consistent with a schema, and report any errors'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or a declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['wb_file'], dict(type=str,
                               help='Path to the workbooks (.csv, .json, .tsv, .xlsx, .yml)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        _, models = get_schema_models(args.schema_file)
        try:
            io.WorkbookReader().run(args.wb_file, models=models, group_objects_by_model=False)
        except ValueError as err:
            raise SystemExit(str(err))
        print('Workbook {} is valid'.format(args.wb_file))


class App(cement.App):
    """ Command line application """
    class Meta:
        label = 'obj-model'
        base_controller = 'base'
        handlers = [
            BaseController,
            ValidateController,
            NormalizeController,
            GenTemplateController,
            GenSchemaController,
            DiffController,
            ConvertController,
        ]


def main():
    with App() as app:
        app.run()


def get_schema_models(filename):
    """ Get a Python schema and its models

    Args:
        filename (:obj:`str`): path to schema or declarative representation of the schema

    Returns:
        :obj:`tuple`:

            * :obj:`types.ModuleType`: schema module
            * :obj:`list` of :obj:`core.Model`: models
    """
    _, ext = os.path.splitext(filename)
    if ext == '.py':
        schema = utils.get_schema(filename)
    else:
        schema = utils.gen_schema(filename)
    models = list(utils.get_models(schema).values())
    return (schema, models)
