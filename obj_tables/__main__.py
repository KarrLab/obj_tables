""" Command line utilities for modeling data in tables (Excel, CSV, TSV)

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-11
:Copyright: 2019, Karr Lab
:License: MIT
"""

from . import core  # noqa: F401
from . import io
from . import utils
import cement
import copy
import obj_tables
import os.path
import types  # noqa: F401

DEFAULT_WRITER_ARGS = {
    'write_empty_cols': False,
}

DEFAULT_READER_ARGS = {
    'allow_multiple_sheets_per_model': True,
    'ignore_missing_models': True,
    'ignore_sheet_order': True,
    'ignore_missing_attributes': True,
    'ignore_attribute_order': True,
}


class BaseController(cement.Controller):
    """ Base controller for command line application """

    class Meta:
        label = 'base'
        description = "Command line utilities for modeling data in tables (Excel, CSV, TSV)"
        help = "Command line utilities for modeling data in tables (Excel, CSV, TSV)"
        arguments = [
            (['-v', '--version'], dict(action='version', version=obj_tables.__version__)),
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
            (['--write-toc'], dict(action='store_true', default=False,
                                   help='If set, write a table of contents with the outputted workbook')),
            (['--write-schema'], dict(action='store_true', default=False,
                                      help='If set, save a copy of the schema within the outputted workbook')),
            (['--unprotected'], dict(action='store_true', default=False,
                                     help='If set, do not protect the outputted workbook')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        schema_name, schema, models = get_schema_models(args.schema_file)
        reader = io.Reader()
        objs = reader.run(args.in_wb_file,
                          schema_name=schema_name,
                          models=models,
                          group_objects_by_model=False,
                          **DEFAULT_READER_ARGS)
        io.Writer().run(args.out_wb_file, objs,
                        schema_name=schema_name,
                        doc_metadata=reader._doc_metadata,
                        model_metadata=reader._model_metadata,
                        models=models, write_toc=args.write_toc, write_schema=args.write_schema,
                        protected=(not args.unprotected),
                        **DEFAULT_WRITER_ARGS)
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
                                 help='Path to the second workbook (.csv, .json, .tsv, .xlsx, .yml)')), ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        schema_name, schema, models = get_schema_models(args.schema_file)
        try:
            diffs = utils.diff_workbooks(args.wb_file_1, args.wb_file_2,
                                         models, args.model,
                                         schema_name=schema_name, **DEFAULT_READER_ARGS)
        except ValueError as err:
            raise SystemExit(str(err))
        if diffs:
            raise SystemExit('\n\n'.join(diffs))
        print('Workbooks are equivalent')


class InitSchemaController(cement.Controller):
    """ Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV) """
    class Meta:
        label = 'init-schema'
        description = 'Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
        help = 'Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'
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
        utils.init_schema(args.in_file, out_filename=args.out_file)
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
            (['--write-toc'], dict(action='store_true', default=False,
                                   help='If set, write a table of contents with the outputted workbook')),
            (['--write-schema'], dict(action='store_true', default=False,
                                      help='If set, save a copy of the schema within the template')),
            (['--unprotected'], dict(action='store_true', default=False,
                                     help='If set, do not protect the outputted workbook')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        schema_name, schema, models = get_schema_models(args.schema_file)
        kw_args = copy.copy(DEFAULT_WRITER_ARGS)
        kw_args['write_empty_cols'] = True
        io.Writer().run(args.template_file, [], schema_name=schema_name, models=models,
                        write_toc=args.write_toc, write_schema=args.write_schema,
                        extra_entries=10, protected=(not args.unprotected),
                        **kw_args)
        print('Template saved to {}'.format(args.template_file))


class NormalizeController(cement.Controller):
    """ Normalize a workbook according to a schema """
    class Meta:
        label = 'normalize'
        description = 'Normalize a workbook according to a schema'
        help = 'Normalize a workbook according to a schema'
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
            (['--write-toc'], dict(action='store_true', default=False,
                                   help='If set, write a table of contents with the outputted workbook')),
            (['--write-schema'], dict(action='store_true', default=False,
                                      help='If set, save a copy of the schema within the normalized workbook')),
            (['--unprotected'], dict(action='store_true', default=False,
                                     help='If set, do not protect the outputted workbook')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        schema_name, schema, models = get_schema_models(args.schema_file)
        for model in models:
            if model.__name__ == args.model:
                break
        if model.__name__ != args.model:
            raise SystemExit('Workbook does not have model "{}"'.format(args.model))

        reader = io.Reader()
        objs = reader.run(args.in_wb_file,
                          schema_name=schema_name,
                          models=models,
                          group_objects_by_model=False,
                          **DEFAULT_READER_ARGS)
        for obj in objs:
            if isinstance(obj, model):
                obj.normalize()
        io.Writer().run(args.out_wb_file, objs,
                        schema_name=schema_name,
                        doc_metadata=reader._doc_metadata,
                        model_metadata=reader._model_metadata,
                        models=models, write_toc=args.write_toc, write_schema=args.write_schema,
                        protected=(not args.unprotected),
                        **DEFAULT_WRITER_ARGS)
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
        schema_name, schema, models = get_schema_models(args.schema_file)
        try:
            io.Reader().run(args.wb_file,
                            schema_name=schema_name,
                            models=models,
                            group_objects_by_model=False,
                            **DEFAULT_READER_ARGS)
        except ValueError as err:
            raise SystemExit(str(err))
        print('Workbook {} is valid'.format(args.wb_file))


class VizSchemaController(cement.Controller):
    """ Generate a UML diagram for a schema """
    class Meta:
        label = 'viz-schema'
        description = 'Generate a UML diagram for a schema'
        help = 'Generate a UML diagram for a schema'
        stacked_on = 'base'
        stacked_type = 'nested'
        arguments = [
            (['schema_file'], dict(type=str,
                                   help='Path to the schema (.py) or a declarative description of the schema (.csv, .tsv, .xlsx)')),
            (['img_file'], dict(type=str,
                                help='Path to save a UML diagram of the schema (.pdf, .png, .svg)')),
        ]

    @cement.ex(hide=True)
    def _default(self):
        args = self.app.pargs
        schema, _ = utils.init_schema(args.schema_file)
        utils.viz_schema(schema, args.img_file)
        print('UML diagram saved to {}'.format(args.img_file))


class App(cement.App):
    """ Command line application """
    class Meta:
        label = 'obj-tables'
        base_controller = 'base'
        handlers = [
            BaseController,
            VizSchemaController,
            ValidateController,
            NormalizeController,
            InitSchemaController,
            GenTemplateController,
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
        * :obj:`str`: schema name
        * :obj:`types.ModuleType`: schema module
        * :obj:`list` of :obj:`core.Model`: models
    """
    _, ext = os.path.splitext(filename)
    if ext == '.py':
        schema = utils.get_schema(filename)
        schema_name = schema.__name__
    else:
        schema, schema_name = utils.init_schema(filename)
    models = list(utils.get_models(schema).values())
    return (schema_name, schema, models)
