""" Test of REST API

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-15
:Copyright: 2019, Karr Lab
:License: MIT
"""

from io import BytesIO
from obj_model import io
from obj_model import rest
from obj_model import utils
import glob
import obj_model
import os
import shutil
import tempfile
import unittest
import wc_utils.workbook.io
import werkzeug.exceptions
import zipfile


class RestTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        # shutil.rmtree(self.tempdir)
        print(self.tempdir)

    def test_PrefixMiddleware(self):
        rest.PrefixMiddleware(rest.app).__call__({'PATH_INFO': 'x'}, lambda x, y: None)

    def test_convert(self):
        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        workbook_filename_1 = os.path.join(self.tempdir, 'file1.xlsx')
        p_0 = schema.Parent(id='p_0')
        p_0.children.create(id='c_0')
        p_0.children.create(id='c_1')
        io.WorkbookWriter().run(workbook_filename_1, [p_0], models=models, sbtab=True)

        client = rest.app.test_client()
        with open(schema_filename, 'rb') as schema_file:
            with open(workbook_filename_1, 'rb') as workbook_file:
                rv = client.post('/api/convert/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (workbook_file, os.path.basename(workbook_filename_1)),
                    'format': 'xlsx',
                    'sbtab': True,
                })
        workbook_filename_2 = os.path.join(self.tempdir, 'file2.xlsx')
        with open(workbook_filename_2, 'wb') as file:
            file.write(rv.data)

        p_0_b = io.WorkbookReader().run(workbook_filename_2,
                                        models=models,
                                        sbtab=True,
                                        **io.SBTAB_DEFAULT_READER_OPTS)[schema.Parent][0]
        self.assertTrue(p_0_b.is_equal(p_0))

    def test_diff(self):
        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        xl_file_1 = os.path.join(self.tempdir, 'file1.xlsx')
        p_0 = schema.Parent(id='p_0')
        p_0.children.create(id='c_0', name='c_0')
        p_0.children.create(id='c_1', name='c_1')
        io.WorkbookWriter().run(xl_file_1, [p_0], models=models, sbtab=True)

        xl_file_2 = os.path.join(self.tempdir, 'file2.xlsx')
        p_0 = schema.Parent(id='p_0')
        p_0.children.create(id='c_0', name='c_0')
        p_0.children.create(id='c_1', name='c_0')
        io.WorkbookWriter().run(xl_file_2, [p_0], models=models, sbtab=True)

        client = rest.app.test_client()

        with open(schema_filename, 'rb') as schema_file:
            with open(xl_file_1, 'rb') as wb_file_1:
                with open(xl_file_1, 'rb') as wb_file_2:
                    rv = client.post('/api/diff/', data={
                        'schema': (schema_file, os.path.basename(schema_filename)),
                        'model': 'Parent',
                        'workbook-1': (wb_file_1, os.path.basename(xl_file_1)),
                        'workbook-2': (wb_file_2, os.path.basename(xl_file_1)),
                        'sbtab': True,
                    })
        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json, [])

        with open(schema_filename, 'rb') as schema_file:
            with open(xl_file_1, 'rb') as wb_file_1:
                with open(xl_file_2, 'rb') as wb_file_2:
                    rv = client.post('/api/diff/', data={
                        'schema': (schema_file, os.path.basename(schema_filename)),
                        'model': 'Parent',
                        'workbook-1': (wb_file_1, os.path.basename(xl_file_1)),
                        'workbook-2': (wb_file_2, os.path.basename(xl_file_2)),
                        'sbtab': True,
                    })
        self.assertEqual(rv.status_code, 200)
        self.assertNotEqual(rv.json, [])

    def test_gen_template(self):
        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        client = rest.app.test_client()
        with open(schema_filename, 'rb') as schema_file:
            rv = client.post('/api/gen-template/', data={
                'schema': (schema_file, os.path.basename(schema_filename)),
                'format': 'xlsx',
                'sbtab': True,
            })
        workbook_filename = os.path.join(self.tempdir, 'file.xlsx')
        with open(workbook_filename, 'wb') as file:
            file.write(rv.data)

        objs = io.WorkbookReader().run(workbook_filename,
                                       models=models,
                                       sbtab=True,
                                       group_objects_by_model=False,
                                       **io.SBTAB_DEFAULT_READER_OPTS)
        self.assertEqual(objs, None)

    def test_init_schema(self):
        client = rest.app.test_client()

        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')

        with open(schema_filename, 'rb') as schema_file:
            rv = client.post('/api/init-schema/', data={
                'schema': (schema_file, os.path.basename(schema_filename)),
                'sbtab': True,
            })
        self.assertEqual(rv.status_code, 200)

        py_file = os.path.join(self.tempdir, 'schema.py')
        with open(py_file, 'wb') as file:
            file.write(rv.data)

        schema = utils.get_schema(py_file)
        self.assertEqual(sorted(utils.get_models(schema)),
                         ['Child', 'Parent', 'Quantity'])

    def test_init_schema_error(self):
        client = rest.app.test_client()

        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')

        with open(schema_filename, 'rb') as schema_file:
            rv = client.post('/api/init-schema/', data={
                'schema': (schema_file, os.path.basename('schema.invalid-ext')),
                'sbtab': True,
            })
        self.assertEqual(rv.status_code, 400)

    def test_normalize(self):
        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        in_workbook_filename = os.path.join(self.tempdir, 'file1.xlsx')
        p_0 = schema.Parent(id='p_0')
        p_0.children.create(id='c_0')
        p_0.children.create(id='c_1')
        io.WorkbookWriter().run(in_workbook_filename, [p_0], models=models, sbtab=True)

        client = rest.app.test_client()

        # to xlsx
        with open(schema_filename, 'rb') as schema_file:
            with open(in_workbook_filename, 'rb') as in_workbook_file:
                rv = client.post('/api/normalize/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'model': 'Parent',
                    'workbook': (in_workbook_file, os.path.basename(in_workbook_filename)),
                    'format': 'xlsx',
                    'sbtab': True,
                })
        out_workbook_file = os.path.join(self.tempdir, 'file2.xlsx')
        with open(out_workbook_file, 'wb') as file:
            file.write(rv.data)

        p_0_b = io.WorkbookReader().run(out_workbook_file,
                                        models=models,
                                        sbtab=True,
                                        **io.SBTAB_DEFAULT_READER_OPTS)[schema.Parent][0]
        self.assertTrue(p_0_b.is_equal(p_0))

        # to tsv
        with open(schema_filename, 'rb') as schema_file:
            with open(in_workbook_filename, 'rb') as in_workbook_file:
                rv = client.post('/api/normalize/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'model': 'Parent',
                    'workbook': (in_workbook_file, os.path.basename(in_workbook_filename)),
                    'format': 'tsv',
                    'sbtab': True,
                })
        out_workbook_file = os.path.join(self.tempdir, '*.tsv')
        with zipfile.ZipFile(BytesIO(rv.data)) as zip_file:
            zip_file.extractall(self.tempdir)

        p_0_b = io.WorkbookReader().run(out_workbook_file,
                                        models=models,
                                        sbtab=True,
                                        **io.SBTAB_DEFAULT_READER_OPTS)[schema.Parent][0]
        self.assertTrue(p_0_b.is_equal(p_0))

    def test_validate(self):
        client = rest.app.test_client()

        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        # valid Excel file
        wb_filename = os.path.join(self.tempdir, 'wb.xlsx')
        p_0 = schema.Parent(id='p_0')
        p_0.children.create(id='c_0')
        p_0.children.create(id='c_1')
        io.WorkbookWriter().run(wb_filename, [p_0], models=models, sbtab=True)

        with open(schema_filename, 'rb') as schema_file:
            with open(wb_filename, 'rb') as wb_file:
                rv = client.post('/api/validate/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (wb_file, os.path.basename(wb_filename)),
                    'sbtab': True,
                })

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json, '')

        # invalid extension
        with open(schema_filename, 'rb') as schema_file:
            with open(wb_filename, 'rb') as wb_file:
                rv = client.post('/api/validate/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (wb_file, os.path.basename(wb_filename) + '-invalid'),
                    'sbtab': True,
                })
        self.assertEqual(rv.status_code, 400)

        # valid csv files
        wb_filename_2 = os.path.join(self.tempdir, '*.csv')
        wb = wc_utils.workbook.io.read(wb_filename)
        wc_utils.workbook.io.write(wb_filename_2, wb)

        wb_filename_3 = os.path.join(self.tempdir, 'wb.zip')
        zip_file = zipfile.ZipFile(wb_filename_3, mode='w')
        for filename in glob.glob(wb_filename_2):
            zip_file.write(filename, arcname=os.path.basename(filename))
        zip_file.close()

        with open(schema_filename, 'rb') as schema_file:
            with open(wb_filename_3, 'rb') as wb_file:
                rv = client.post('/api/validate/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (wb_file, os.path.basename(wb_filename_3)),
                    'sbtab': True,
                })

        self.assertEqual(rv.status_code, 200)
        self.assertEqual(rv.json, '')

        # invalid tsv files
        wb_filename_4 = os.path.join(self.tempdir, '*.tsv')
        wb = wc_utils.workbook.io.read(wb_filename)
        wb['!Child'][4][0] = 'c_0'
        wc_utils.workbook.io.write(wb_filename_4, wb)

        wb_filename_5 = os.path.join(self.tempdir, 'wb2.zip')
        zip_file = zipfile.ZipFile(wb_filename_5, mode='w')
        for filename in glob.glob(wb_filename_4):
            zip_file.write(filename, arcname=os.path.basename(filename))
        zip_file.close()

        with open(schema_filename, 'rb') as schema_file:
            with open(wb_filename_5, 'rb') as wb_file:
                rv = client.post('/api/validate/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (wb_file, os.path.basename(wb_filename_5)),
                    'sbtab': True,
                })

        self.assertEqual(rv.status_code, 200)
        self.assertNotEqual(rv.json, '')

        # invalid csv and tsv files
        wb_filename_6 = os.path.join(self.tempdir, 'wb3.zip')
        zip_file = zipfile.ZipFile(wb_filename_6, mode='w')
        for filename in glob.glob(wb_filename_2):
            zip_file.write(filename, arcname=os.path.basename(filename))
        for filename in glob.glob(wb_filename_4):
            zip_file.write(filename, arcname=os.path.basename(filename))
        zip_file.close()

        with open(schema_filename, 'rb') as schema_file:
            with open(wb_filename_6, 'rb') as wb_file:
                rv = client.post('/api/validate/', data={
                    'schema': (schema_file, os.path.basename(schema_filename)),
                    'workbook': (wb_file, os.path.basename(wb_filename_6)),
                    'sbtab': True,
                })

        self.assertEqual(rv.status_code, 400)

    def test_get_model(self):
        schema_filename = os.path.join('tests', 'fixtures', 'schema.csv')
        schema = utils.init_schema(schema_filename, sbtab=True)
        models = list(utils.get_models(schema).values())

        with self.assertRaises(werkzeug.exceptions.BadRequest):
            rest.get_model(models, 'Parent2')
