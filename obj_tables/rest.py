""" REST API

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-15
:Copyright: 2019, Karr Lab
:License: MIT
"""

from . import core
from . import io
from . import utils
from .__main__ import get_schema_models, DEFAULT_WRITER_ARGS, DEFAULT_READER_ARGS
from wc_utils.util.string import indent_forest
from werkzeug.datastructures import FileStorage
import copy
import flask
import flask_cors
import flask_restplus
import flask_restplus.errors
import flask_restplus.fields
import flask_restplus.inputs
import glob
import obj_tables
import os
import shutil
import tempfile
import zipfile

# setup app
app = flask.Flask(__name__)
cors = flask_cors.CORS(app,
                       resources={r"/*": {"origins": "*"}},
                       expose_headers=["content-disposition"])


class PrefixMiddleware(object):
    def __init__(self, app, prefix=''):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.prefix):
            environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
            environ['SCRIPT_NAME'] = self.prefix
            return self.app(environ, start_response)
        else:
            start_response('404', [('Content-Type', 'text/plain')])
            return ["This url does not belong to the app.".encode()]


app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/api')

api = flask_restplus.Api(app,
                         title='ObjTables REST API',
                         description='REST API for generating and working with schemas for tabular-formatted datasets',
                         contact='info@karrlab.org',
                         version=obj_tables.__version__,
                         license='MIT',
                         license_url='https://github.com/KarrLab/obj_tables/blob/master/LICENSE',
                         doc='/')

""" Convert """
convert_parser = api.parser()
convert_parser.add_argument('schema', location='files',
                            type=FileStorage,
                            required=True,
                            help='Schema file (.csv, .tsv, .xlsx)')
convert_parser.add_argument('workbook', location='files',
                            type=FileStorage,
                            required=True,
                            help='Workbook (.csv, .tsv, .zip of .csv or .tsv, .xlsx)')
convert_parser.add_argument('format',
                            type=flask_restplus.inputs.regex(r'^(csv|tsv|xlsx)$'),
                            default='xlsx',
                            required=False,
                            help='Format to convert workbook')
convert_parser.add_argument('write-toc',
                            type=flask_restplus.inputs.boolean,
                            default=False,
                            required=False,
                            help='If true, save table of contents with file')
convert_parser.add_argument('write-schema',
                            type=flask_restplus.inputs.boolean,
                            default=False,
                            required=False,
                            help='If true, save schema with file')
convert_parser.add_argument('protected',
                            type=flask_restplus.inputs.boolean,
                            default=True,
                            required=False,
                            help='If true, protect the table headings in the file from editing')


@api.route("/convert/",
           doc={'description': 'Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML)'})
@api.expect(convert_parser)
class Convert(flask_restplus.Resource):
    """ Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML) """

    def post(self):
        """ Convert a schema-encoded workbook to another format (CSV, Excel, JSON, TSV, YAML)
        """
        """
        Returns:
            :obj:`flask.Response`: response with workbook
        """
        args = convert_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])
        in_wb_dir, in_wb_filename = save_in_workbook(args['workbook'])
        format = args['format']

        try:
            schema_name, schema, models = get_schema_models(schema_filename)
            objs, doc_metadata, model_metadata = read_workbook(in_wb_filename, models, schema_name=schema_name)
            out_wb_dir, out_wb_filename, out_wb_mimetype = save_out_workbook(
                format, objs, schema_name, doc_metadata, model_metadata, models=models,
                write_toc=args['write-toc'],
                write_schema=args['write-schema'],
                protected=args['protected'],
                **DEFAULT_WRITER_ARGS)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)
            shutil.rmtree(in_wb_dir)

        @flask.after_this_request
        def remove_out_file(response):
            shutil.rmtree(out_wb_dir)
            return response

        return flask.send_file(out_wb_filename,
                               attachment_filename=os.path.basename(out_wb_filename),
                               mimetype=out_wb_mimetype,
                               as_attachment=True)


""" Difference """
diff_parser = api.parser()
diff_parser.add_argument('schema', location='files',
                         type=FileStorage,
                         required=True,
                         help='Schema file (.csv, .tsv, .xlsx)')
diff_parser.add_argument('model',
                         type=str,
                         required=True,
                         help='Type of objects to compare')
diff_parser.add_argument('workbook', location='files',
                         type=FileStorage,
                         required=True,
                         help='First workbook (.csv, .tsv, .zip of .csv or .tsv, .xlsx)')
diff_parser.add_argument('workbook-2', location='files',
                         type=FileStorage,
                         required=True,
                         help='Second workbook (.csv, .tsv, .zip of .csv or .tsv, .xlsx)')


@api.route("/diff/",
           doc={'description': 'Calculate the difference between two workbooks according to a schema'})
@api.expect(diff_parser)
class Diff(flask_restplus.Resource):
    """ Calculate the difference between two workbooks according to a schema """

    def post(self):
        """ Calculate the difference between two workbooks according to a schema
        """
        """
        Returns:
            :obj:`list` of :obj:`str`: list of difference between workbooks
        """
        args = diff_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])
        model_name = args['model']
        wb_dir_1, wb_filename_1 = save_in_workbook(args['workbook'])
        wb_dir_2, wb_filename_2 = save_in_workbook(args['workbook-2'])

        try:
            schema_name, schema, models = get_schema_models(schema_filename)
        except Exception as err:
            shutil.rmtree(schema_dir)
            shutil.rmtree(wb_dir_1)
            shutil.rmtree(wb_dir_2)
            flask_restplus.abort(400, str(err))

        try:
            diffs = utils.diff_workbooks(wb_filename_1, wb_filename_2,
                                         models, model_name,
                                         schema_name=schema_name,
                                         **DEFAULT_READER_ARGS)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)
            shutil.rmtree(wb_dir_1)
            shutil.rmtree(wb_dir_2)

        return diffs


""" Generate template """
gen_template_parser = api.parser()
gen_template_parser.add_argument('schema', location='files',
                                 type=FileStorage,
                                 required=True,
                                 help='Schema file (.csv, .tsv, .xlsx)')
gen_template_parser.add_argument('format',
                                 type=flask_restplus.inputs.regex(r'^(csv|tsv|xlsx)$'),
                                 default='xlsx',
                                 required=False,
                                 help='Format for template')
gen_template_parser.add_argument('write-toc',
                                 type=flask_restplus.inputs.boolean,
                                 default=False,
                                 required=False,
                                 help='If true, save table of contents with file')
gen_template_parser.add_argument('write-schema',
                                 type=flask_restplus.inputs.boolean,
                                 default=False,
                                 required=False,
                                 help='If true, save schema with file')
gen_template_parser.add_argument('protected',
                                 type=flask_restplus.inputs.boolean,
                                 default=True,
                                 required=False,
                                 help='If true, protect the table headings in the file from editing')


@api.route("/gen-template/",
           doc={'description': 'Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema'})
@api.expect(gen_template_parser)
class GenTemplate(flask_restplus.Resource):
    """ Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema """

    def post(self):
        """ Generate a template workbook (Excel, CSV, TSV) for a schema or declarative description of a schema
        """
        """
        Returns:
            :obj:`flask.Response`: response with workbook
        """
        args = gen_template_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])
        format = args['format']

        try:
            schema_name, schema, models = get_schema_models(schema_filename)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)

        kw_args = copy.copy(DEFAULT_WRITER_ARGS)
        kw_args['write_empty_cols'] = True
        out_wb_dir, out_wb_filename, out_wb_mimetype = save_out_workbook(
            format, [], schema_name, {}, {}, models=models,
            write_toc=args['write-toc'],
            write_schema=args['write-schema'],
            protected=args['protected'],
            **kw_args)

        @flask.after_this_request
        def remove_out_file(response):
            shutil.rmtree(out_wb_dir)
            return response

        return flask.send_file(out_wb_filename,
                               attachment_filename=os.path.basename(out_wb_filename),
                               mimetype=out_wb_mimetype,
                               as_attachment=True)


""" Init schema """
init_schema_parser = api.parser()
init_schema_parser.add_argument('schema', location='files',
                                type=FileStorage,
                                required=True,
                                help='File with tabular description of schema (.csv, .tsv, .xlsx)')


@api.route("/init-schema/",
           doc={'description': 'Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)'})
@api.expect(init_schema_parser)
class InitSchema(flask_restplus.Resource):
    """ Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV) """

    def post(self):
        """ Initialize a Python schema from a declarative description of the schema in a table (Excel, CSV, TSV)
        """
        """
        Returns:
            :obj:`flask.Response`: response with Python schema
        """
        args = init_schema_parser.parse_args()

        schema_dir, schema_filename = save_schema(args['schema'])

        py_schema_dir = tempfile.mkdtemp()
        py_schema_filename = os.path.join(py_schema_dir, 'schema.py')

        try:
            utils.init_schema(schema_filename,
                              out_filename=py_schema_filename)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)

            @flask.after_this_request
            def remove_out_file(response):
                shutil.rmtree(py_schema_dir)
                return response

        return flask.send_file(py_schema_filename,
                               attachment_filename='schema.py',
                               mimetype='text/x-python',
                               as_attachment=True)


""" Normalize """
norm_parser = api.parser()
norm_parser.add_argument('schema', location='files',
                         type=FileStorage,
                         required=True,
                         help='Schema file (.csv, .tsv, .xlsx)')
norm_parser.add_argument('model',
                         type=str,
                         required=True,
                         help='Type of objects to normalize')
norm_parser.add_argument('workbook', location='files',
                         type=FileStorage,
                         required=True,
                         help='Workbook (.csv, .tsv, .zip of .csv or .tsv, .xlsx)')
norm_parser.add_argument('format',
                         type=flask_restplus.inputs.regex(r'^(csv|tsv|xlsx)$'),
                         default='xlsx',
                         required=False,
                         help='Format for normalized workbook')
norm_parser.add_argument('write-toc',
                         type=flask_restplus.inputs.boolean,
                         default=False,
                         required=False,
                         help='If true, save table of contents with file')
norm_parser.add_argument('write-schema',
                         type=flask_restplus.inputs.boolean,
                         default=False,
                         required=False,
                         help='If true, save schema with file')
norm_parser.add_argument('protected',
                         type=flask_restplus.inputs.boolean,
                         default=True,
                         required=False,
                         help='If true, protect the table headings in the file from editing')


@api.route("/normalize/",
           doc={'description': 'Normalize a workbook according to a schema'})
@api.expect(norm_parser)
class Normalize(flask_restplus.Resource):
    """ Normalize a workbook according to a schema """

    def post(self):
        """ Normalize a workbook according to a schema
        """
        """
        Returns:
            :obj:`flask.Response`: response with workbook
        """
        args = norm_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])
        model_name = args['model']
        in_wb_dir, in_wb_filename = save_in_workbook(args['workbook'])
        format = args['format']

        try:
            schema_name, schema, models = get_schema_models(schema_filename)
        except Exception as err:
            shutil.rmtree(schema_dir)
            shutil.rmtree(in_wb_dir)
            flask_restplus.abort(400, str(err))

        model = get_model(models, model_name)

        try:
            objs, doc_metadata, model_metadata = read_workbook(in_wb_filename, models, schema_name=schema_name)
            for obj in objs:
                if isinstance(obj, model):
                    obj.normalize()
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)
            shutil.rmtree(in_wb_dir)

        out_wb_dir, out_wb_filename, out_wb_mimetype = save_out_workbook(
            format, objs, schema_name, doc_metadata, model_metadata, models=models,
            write_toc=args['write-toc'],
            write_schema=args['write-schema'],
            protected=args['protected'],
            **DEFAULT_WRITER_ARGS)

        @flask.after_this_request
        def remove_out_file(response):
            shutil.rmtree(out_wb_dir)
            return response

        return flask.send_file(out_wb_filename,
                               attachment_filename=os.path.basename(out_wb_filename),
                               mimetype=out_wb_mimetype,
                               as_attachment=True)


""" Validate """
validate_parser = api.parser()
validate_parser.add_argument('schema', location='files',
                             type=FileStorage,
                             required=True,
                             help='Schema file (.csv, .tsv, .xlsx)')
validate_parser.add_argument('workbook', location='files',
                             type=FileStorage,
                             required=True,
                             help='Workbook (.csv, .tsv, .zip of .csv or .tsv, .xlsx)')


@api.route("/validate/")
@api.expect(validate_parser,
            doc={'description': 'Validate that a workbook is consistent with a schema, and report any errors'})
class Validate(flask_restplus.Resource):
    """ Validate that a workbook is consistent with a schema, and report any errors """

    def post(self):
        """ Validate that a workbook is consistent with a schema, and report any errors
        """
        """
        Returns:
            :obj:`str`: errors
        """
        args = validate_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])
        wb_dir, wb_filename = save_in_workbook(args['workbook'])

        try:
            schema_name, schema, models = get_schema_models(schema_filename)
            objs = io.Reader().run(wb_filename,
                                   schema_name=schema_name,
                                   models=models,
                                   group_objects_by_model=False,
                                   validate=False,
                                   **DEFAULT_READER_ARGS)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)
            shutil.rmtree(wb_dir)

        errors = core.Validator().validate(objs)
        if errors:
            err_msg = indent_forest(['The dataset is invalid:', [errors]])
        else:
            err_msg = ''

        return err_msg


""" Visualize schema """
viz_parser = api.parser()
viz_parser.add_argument('schema', location='files',
                        type=FileStorage,
                        required=True,
                        help='Schema file (.csv, .tsv, .xlsx)')
viz_parser.add_argument('format',
                        type=flask_restplus.inputs.regex(r'^(pdf|png|svg)$'),
                        default='svg',
                        required=False,
                        help='Format for UML diagram')


@api.route("/viz-schema/")
@api.expect(viz_parser,
            doc={'description': 'Generate a UML diagram for a schema'})
class VizSchema(flask_restplus.Resource):
    """ Generate a UML diagram for a schema """

    def post(self):
        """ Generate a UML diagram for a schema
        """
        """
        Returns:
            :obj:`str`: errors
        """
        args = viz_parser.parse_args()
        schema_dir, schema_filename = save_schema(args['schema'])

        try:
            schema, _ = utils.init_schema(schema_filename)
        except Exception as err:
            flask_restplus.abort(400, str(err))
        finally:
            shutil.rmtree(schema_dir)

        format = args['format']
        img_dir = tempfile.mkdtemp()
        img_file = os.path.join(img_dir, 'schema.' + format)
        try:
            utils.viz_schema(schema, img_file)
        except Exception as err:
            shutil.rmtree(img_dir)
            flask_restplus.abort(400, str(err))

        @flask.after_this_request
        def remove_out_file(response):
            shutil.rmtree(img_dir)
            return response

        if format == 'pdf':
            mimetype = 'application/pdf'
        elif format == 'png':
            mimetype = 'image/png'
        elif format == 'svg':
            mimetype = 'image/svg+xml'

        return flask.send_file(img_file,
                               attachment_filename=os.path.basename(img_file),
                               mimetype=mimetype,
                               as_attachment=True)


def save_schema(file_storage):
    """ Save schema to a temporary directory

    Args:
        file_storage (:obj:`FileStorage`): uploaded file

    Returns:
        :obj:`tuple`:

            * :obj:`str`: temporary directory with schema
            * :obj:`str`: local path to schema file
    """
    if os.path.splitext(file_storage.filename)[1] not in ['.csv', '.tsv', '.xlsx']:
        flask_restplus.abort(400, 'Schema must be a .csv, .tsv or .xlsx file.')

    dir = tempfile.mkdtemp()
    filename = os.path.join(dir, file_storage.filename)
    file_storage.save(filename)
    file_storage.close()

    return dir, filename


def save_in_workbook(file_storage):
    """ Save workbook to a temporary directory

    Args:
        file_storage (:obj:`FileStorage`): uploaded file

    Returns:
        :obj:`tuple`:

            * :obj:`str`: temporary directory with workbook
            * :obj:`str`: local path to workbook file
    """
    if os.path.splitext(file_storage.filename)[1] not in ['.csv', '.tsv', '.xlsx', '.zip']:
        flask_restplus.abort(400, 'Workbook must be a .csv, .tsv .xlsx, or .zip file.')

    dir = tempfile.mkdtemp()

    if os.path.splitext(file_storage.filename)[1] == '.zip':
        zip_file_dir = tempfile.mkdtemp()
        zip_filename = os.path.join(zip_file_dir, 'tmp.zip')
        file_storage.save(zip_filename)
        file_storage.close()

        with zipfile.ZipFile(zip_filename, 'r') as zip_file:
            has_csv = False
            has_tsv = False
            for f in zip_file.infolist():
                has_csv = has_csv or os.path.splitext(f.filename)[1] == '.csv'
                has_tsv = has_tsv or os.path.splitext(f.filename)[1] == '.tsv'
            if (has_csv and has_tsv) or (not has_csv and not has_tsv):
                flask_restplus.abort(400, 'Workbook must contain .csv or .tsv files.')
            if has_csv:
                filename = os.path.join(dir, '*.csv')
            else:
                filename = os.path.join(dir, '*.tsv')
            zip_file.extractall(dir)

        shutil.rmtree(zip_file_dir)
    else:
        filename = os.path.join(dir, file_storage.filename)
        file_storage.save(filename)
        file_storage.close()

    return (dir, filename)


def read_workbook(filename, models, schema_name=None):
    """ Read a workbook

    Args:
        filename (:obj:`str`): path to workbook
        models (:obj:`list` of :obj:`core.Model`): models
        schema_name (:obj:str`, optional): schema name

    Returns:
        :obj:`tuple`:

            * :obj:`dict`: dictionary that maps types to a dictionary of instance
            * :obj:`dict`: dictionary of model metadata
    """
    reader = io.Reader()
    result = reader.run(filename,
                        schema_name=schema_name,
                        models=models,
                        group_objects_by_model=False,
                        **DEFAULT_READER_ARGS)
    return result, reader._doc_metadata, reader._model_metadata


def save_out_workbook(format, objs, schema_name, doc_metadata, model_metadata, models,
                      write_toc=False, write_schema=False, write_empty_cols=True, protected=True):
    """
    Args:
        format (:obj:`str`): format (.csv, .tsv, .xlsx)
        objs (:obj:`dict`): dictionary that maps types to instances
        schema_name (:obj:`str`): schema name
        doc_metadata (:obj:`dict`): dictionary of document metadata
        model_metadata (:obj:`dict`): dictionary of model metadata
        models (:obj:`list` of :obj:`core.Model`): models
        write_toc (:obj:`bool`, optional): if :obj:`True`, write
            a table of contents with the file
        write_schema (:obj:`bool`, optional): if :obj:`True`, write
            schema with file
        write_empty_cols (:obj:`bool`, optional): if :obj:`True`, write columns even when all values are :obj:`None`
        protected (:obj:`bool`, optional): if :obj:`True`, protect the worksheet

    Returns:
        :obj:`tuple`:

            * :obj:`str`: temporary directory with workbook
            * :obj:`str`: path to workbook file
            * :obj:`str`: mimetype of workbook
    """
    dir = tempfile.mkdtemp()
    if format in ['csv', 'tsv']:
        temp_filename = os.path.join(dir, '*.' + format)
    else:
        temp_filename = os.path.join(dir, 'workbook.' + format)

    io.Writer().run(temp_filename, objs, schema_name=schema_name, doc_metadata=doc_metadata, model_metadata=model_metadata,
                    models=models, write_toc=write_toc, write_schema=write_schema, protected=protected)

    if format in ['csv', 'tsv']:
        filename = os.path.join(dir, 'workbook.{}.zip'.format(format))
        mimetype = 'application/zip'
        with zipfile.ZipFile(filename, 'w') as zip_file:
            for temp_model_filename in glob.glob(temp_filename):
                zip_file.write(temp_model_filename, os.path.basename(temp_model_filename))
    else:
        filename = temp_filename
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    return dir, filename, mimetype


def get_model(models, name):
    """ Get the model with name :obj:`name`

    Args:
        models (:obj:`list` of :obj:`core.Model`): models
        name (:obj:`str`): model name

    Returns:
        :obj:`core.Model`: model
    """
    for model in models:
        if model.__name__ == name:
            break
    if model.__name__ != name:
        flask_restplus.abort(400, 'Workbook does not have model "{}".'.format(name))
    return model
