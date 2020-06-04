""" Test examples

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-09-18
:Copyright: 2019, Karr Lab
:License: MIT
"""

from obj_tables import __main__
from obj_tables import core
from obj_tables import io
from obj_tables import utils
import glob
import importlib
import json
import nbconvert.preprocessors
import nbformat
import obj_tables
import os
import shutil
import sys
import tempfile
import unittest


class ExamplesTestCase(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, 'examples')
        sys.path.append('examples/address_book')
        self.dirname = tempfile.mkdtemp()

    def tearDown(self):
        sys.path.remove('examples')
        sys.path.remove('examples/address_book')
        shutil.rmtree(self.dirname)

    def test_web_tutorial(self):
        import tutorial
        tutorial.run()

    def test_biochemical_model_example(self):
        dirname = 'examples/biochemical_model'
        schema_filename_xlsx = os.path.join(dirname, 'schema.xlsx')
        data_filename_xlsx = os.path.join(dirname, 'data.xlsx')

        data_copy_filename_xlsx = os.path.join(dirname, 'data_copy.xlsx')
        with __main__.App(argv=['convert', schema_filename_xlsx, data_filename_xlsx, data_copy_filename_xlsx]) as app:
            app.run()

        with __main__.App(argv=['diff', schema_filename_xlsx, 'Model', data_filename_xlsx, data_copy_filename_xlsx]) as app:
            app.run()

        os.remove(data_copy_filename_xlsx)

    def test_sbtab_sbml_validate_examples(self):
        self.do_sbtab_sbml_examples('validate')

    def test_sbtab_sbml_convert_examples(self):
        self.do_sbtab_sbml_examples('convert')

    def do_sbtab_sbml_examples(self, action):
        dirname = os.path.join('examples', 'sbtab')
        schema_filename = os.path.join(dirname, 'SBtab.csv')

        # Initalize Python module which implements schema
        py_module_filename = os.path.join(dirname, 'SBtab.py')
        with __main__.App(argv=['init-schema', schema_filename, py_module_filename]) as app:
            app.run()

        # Visualize schema
        diagram_filename = os.path.join(dirname, 'SBtab.svg')
        with __main__.App(argv=['viz-schema', schema_filename, diagram_filename]) as app:
            app.run()

        # Generate a template for the schema
        template_filename = os.path.join(dirname, 'template.xlsx')
        with __main__.App(argv=['gen-template', schema_filename, template_filename,
                                '--write-schema',
                                '--write-toc'
                                ]) as app:
            app.run()

        # Validate that documents adhere to the schema
        data_filenames = [
            'template.xlsx',
            'hynne/*.tsv',
            'hynne.tsv',
            'lac_operon/*.tsv',
            'feed_forward_loop_relationship.tsv',
            'kegg_reactions_cc_ph70_quantity.tsv',
            'yeast_transcription_network_chang_2008_relationship.tsv',
            'simple_examples/1.tsv',
            'simple_examples/2.csv',
            'simple_examples/3.csv',
            'simple_examples/4.csv',
            'simple_examples/5.csv',
            'simple_examples/6.csv',
            'simple_examples/7.csv',
            'simple_examples/8.csv',
            'simple_examples/9.csv',
            'simple_examples/10.csv',
            'teusink_data.tsv',
            'teusink_model.tsv',
            'jiang_data.tsv',
            'jiang_model.tsv',
            'ecoli_noor_2016_data.tsv',
            'ecoli_noor_2016_model.tsv',
            'ecoli_wortel_2018_data.tsv',
            'ecoli_wortel_2018_model.tsv',
            'sigurdsson_model.tsv',
            'layout_model.tsv',
        ]
        for data_filename in data_filenames:
            full_data_filename = os.path.join(dirname, data_filename)

            if action == 'validate':
                with __main__.App(argv=['validate', schema_filename, full_data_filename]) as app:
                    app.run()

            if action == 'convert' and not data_filename.endswith('.xlsx'):
                convert_filename = data_filename \
                    .replace('/*', '') \
                    .replace('.csv', '.xlsx') \
                    .replace('.tsv', '.xlsx')
                full_convert_filename = os.path.join('examples', 'sbtab', convert_filename)
                with __main__.App(argv=['convert', schema_filename, full_data_filename,
                                        full_convert_filename, ]) as app:
                    app.run()

    def test_metabolomics_examples(self):
        dirnames = [
            'examples/metabolic_kinetics',
            'examples/metabolic_thermodynamics',
        ]
        for dirname in dirnames:
            schema_filename_csv = os.path.join(dirname, 'schema.csv')
            schema_filename_tsv = os.path.join(dirname, 'schema.tsv')
            schema_filename_xlsx = os.path.join(dirname, 'schema.xlsx')
            schema_filename_py = os.path.join(dirname, 'schema.py')
            schema_filename_svg = os.path.join(dirname, 'schema.svg')
            template_filename = os.path.join(dirname, 'template.xlsx')
            data_filename_csv = os.path.join(dirname, 'data.csv/*.csv')
            data_filename_tsv = os.path.join(dirname, 'data.tsv/*.tsv')
            data_filename_multi_csv = os.path.join(dirname, 'data.multi.csv')
            data_filename_multi_tsv = os.path.join(dirname, 'data.multi.tsv')
            data_filename_xlsx = os.path.join(dirname, 'data.xlsx')
            data_filename_json = os.path.join(dirname, 'data.json')
            data_filename_yml = os.path.join(dirname, 'data.yml')
            schema_data_filename_xlsx = os.path.join(dirname, 'schema_and_data.xlsx')
            schema_data_filename_csv = os.path.join(dirname, 'schema_and_data.multi.csv')
            schema_data_filename_tsv = os.path.join(dirname, 'schema_and_data.multi.tsv')

            if not os.path.isdir(os.path.dirname(data_filename_csv)):
                os.mkdir(os.path.dirname(data_filename_csv))
            if not os.path.isdir(os.path.dirname(data_filename_tsv)):
                os.mkdir(os.path.dirname(data_filename_tsv))

            with __main__.App(argv=['viz-schema', schema_filename_csv, schema_filename_svg]) as app:
                app.run()

            with __main__.App(argv=['gen-template', schema_filename_csv, template_filename,
                                    '--write-toc', '--write-schema']) as app:
                app.run()

            with __main__.App(argv=['validate', schema_filename_csv, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_tsv, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_xlsx, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_py, data_filename_xlsx]) as app:
                app.run()

            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_csv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_tsv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_multi_csv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_multi_tsv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_json]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_yml]) as app:
                app.run()

            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_csv, '--write-toc', '--write-schema']) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_tsv, '--write-toc', '--write-schema']) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_xlsx, '--write-toc', '--write-schema']) as app:
                app.run()

    def test_metabolomics_example_merging(self):
        loader = importlib.machinery.SourceFileLoader('run', 'examples/metabolic_merged/run.py')
        module = loader.load_module()
        if os.path.isfile(module.PLOT_FILENAME):
            os.remove(module.PLOT_FILENAME)
        module.plot_data()
        self.assertTrue(os.path.isfile(module.PLOT_FILENAME))

    def test_other_examples(self):
        dirnames = [
            'examples/address_book',
            'examples/biochemical_model',
            'examples/children_fav_games',
            'examples/financial_transactions',
            'examples/genomics',
        ]
        for dirname in dirnames:
            schema_filename_csv = os.path.join(dirname, 'schema.csv')
            schema_filename_tsv = os.path.join(dirname, 'schema.tsv')
            schema_filename_xlsx = os.path.join(dirname, 'schema.xlsx')
            schema_filename_py = os.path.join(dirname, 'schema.py')
            schema_filename_svg = os.path.join(dirname, 'schema.svg')
            template_filename = os.path.join(dirname, 'template.xlsx')
            data_filename_csv = os.path.join(dirname, 'data.csv/*.csv')
            data_filename_tsv = os.path.join(dirname, 'data.tsv/*.tsv')
            data_filename_multi_csv = os.path.join(dirname, 'data.multi.csv')
            data_filename_multi_tsv = os.path.join(dirname, 'data.multi.tsv')
            data_filename_xlsx = os.path.join(dirname, 'data.xlsx')
            data_filename_json = os.path.join(dirname, 'data.json')
            data_filename_yml = os.path.join(dirname, 'data.yml')
            schema_data_filename_xlsx = os.path.join(dirname, 'schema_and_data.xlsx')
            schema_data_filename_csv = os.path.join(dirname, 'schema_and_data.multi.csv')
            schema_data_filename_tsv = os.path.join(dirname, 'schema_and_data.multi.tsv')

            if not os.path.isdir(os.path.dirname(data_filename_csv)):
                os.mkdir(os.path.dirname(data_filename_csv))
            if not os.path.isdir(os.path.dirname(data_filename_tsv)):
                os.mkdir(os.path.dirname(data_filename_tsv))

            with __main__.App(argv=['init-schema', schema_filename_csv, schema_filename_py]) as app:
                app.run()

            with __main__.App(argv=['viz-schema', schema_filename_csv, schema_filename_svg]) as app:
                app.run()

            with __main__.App(argv=['gen-template', schema_filename_csv, template_filename,
                                    '--write-toc', '--write-schema']) as app:
                app.run()

            with __main__.App(argv=['validate', schema_filename_csv, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_tsv, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_xlsx, data_filename_xlsx]) as app:
                app.run()
            with __main__.App(argv=['validate', schema_filename_py, data_filename_xlsx]) as app:
                app.run()

            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_csv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_tsv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_multi_csv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_multi_tsv]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_json]) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx, data_filename_yml]) as app:
                app.run()

            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_csv, '--write-toc', '--write-schema']) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_tsv, '--write-toc', '--write-schema']) as app:
                app.run()
            with __main__.App(argv=['convert', schema_filename_csv, data_filename_xlsx,
                                    schema_data_filename_xlsx, '--write-toc', '--write-schema']) as app:
                app.run()

    def test_wc_kb_lang(self):
        import wc_kb
        import wc_lang

        diagram_filename = os.path.join('examples', 'wc_kb.eukaryote.svg')
        if os.path.isfile(diagram_filename):
            os.remove(diagram_filename)
        utils.viz_schema(wc_kb.eukaryote, diagram_filename)
        self.assertTrue(os.path.isfile(diagram_filename))

        diagram_filename = os.path.join('examples', 'wc_kb.prokaryote.svg')
        if os.path.isfile(diagram_filename):
            os.remove(diagram_filename)
        utils.viz_schema(wc_kb.prokaryote, diagram_filename)
        self.assertTrue(os.path.isfile(diagram_filename))

        diagram_filename = os.path.join('examples', 'wc_lang.svg')
        if os.path.isfile(diagram_filename):
            os.remove(diagram_filename)
        utils.viz_schema(wc_lang.core, diagram_filename)
        self.assertTrue(os.path.isfile(diagram_filename))

    def test_decode_data(self):
        import decode_data

        class Parent(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()

        class Child(core.Model):
            id = core.SlugAttribute()
            name = core.StringAttribute()
            parents = core.ManyToManyAttribute(Parent, related_name='children')

        p1 = Parent(id='p1', name='P1')
        p2 = Parent(id='p2', name='P2')
        c1 = Child(id='c1', name='C1', parents=[p1, p2])
        c2 = Child(id='c2', name='C2', parents=[p1])
        c3 = Child(id='c3', name='C3', parents=[p2])

        filename = os.path.join(self.dirname, 'test.json')
        io.JsonWriter().run(filename, [p1, p2, c1, c2, c3], validate=False)

        with open(filename, 'r') as file:
            json_dict = json.load(file)
            decoded = decode_data.decode_data(json_dict)

        p1_b = {'__type': 'Parent', 'id': 'p1', 'name': 'P1'}
        p2_b = {'__type': 'Parent', 'id': 'p2', 'name': 'P2'}
        c1_b = {'__type': 'Child', 'id': 'c1', 'name': 'C1'}
        c2_b = {'__type': 'Child', 'id': 'c2', 'name': 'C2'}
        c3_b = {'__type': 'Child', 'id': 'c3', 'name': 'C3'}
        p1_b['children'] = [c1_b, c2_b]
        p2_b['children'] = [c1_b, c3_b]
        c1_b['parents'] = [p1_b, p2_b]
        c2_b['parents'] = [p1_b]
        c3_b['parents'] = [p2_b]

        self.assertEqual(sorted(decoded.keys()), ['Child', 'Parent', "_classMetadata", "_documentMetadata"])
        self.assertEqual(len(decoded['Parent']), 2)
        self.assertEqual(len(decoded['Child']), 3)
        parents_b = sorted(decoded['Parent'], key=lambda p: p['id'])
        children_b = sorted(decoded['Child'], key=lambda c: c['id'])
        for i_parent, parent in enumerate(parents_b):
            self.assertEqual(sorted(parent.keys()), ['__type', 'children', 'id', 'name'])
            self.assertEqual(parent['__type'], 'Parent')
            self.assertEqual(parent['id'], 'p' + str(i_parent + 1))
            self.assertEqual(parent['name'], 'P' + str(i_parent + 1))
        for i_child, child in enumerate(children_b):
            self.assertEqual(sorted(child.keys()), ['__type', 'id', 'name', 'parents'])
            self.assertEqual(child['__type'], 'Child')
            self.assertEqual(child['id'], 'c' + str(i_child + 1))
            self.assertEqual(child['name'], 'C' + str(i_child + 1))

        self.assertEqual(sorted(parents_b[0]['children'], key=lambda c: c['id']), [children_b[0], children_b[1]])
        self.assertEqual(sorted(parents_b[1]['children'], key=lambda c: c['id']), [children_b[0], children_b[2]])
        self.assertEqual(sorted(children_b[0]['parents'], key=lambda p: p['id']), [parents_b[0], parents_b[1]])
        self.assertEqual(sorted(children_b[1]['parents'], key=lambda p: p['id']), [parents_b[0]])
        self.assertEqual(sorted(children_b[2]['parents'], key=lambda p: p['id']), [parents_b[1]])

        self.assertEqual(parents_b[0]['children'], [children_b[0], children_b[1]])
        self.assertEqual(parents_b[1]['children'], [children_b[0], children_b[2]])
        self.assertEqual(children_b[0]['parents'], [parents_b[0], parents_b[1]])
        self.assertEqual(children_b[1]['parents'], [parents_b[0]])
        self.assertEqual(children_b[2]['parents'], [parents_b[1]])

    NOTEBOOK_TIMEOUT = 600

    def test_jupyter_tutorials(self):
        for filename in glob.glob('examples/tutorials/*.ipynb'):
            with open(filename) as file:
                version = json.load(file)['nbformat']
            with open(filename) as file:
                notebook = nbformat.read(file, as_version=version)
            execute_preprocessor = nbconvert.preprocessors.ExecutePreprocessor(timeout=self.NOTEBOOK_TIMEOUT)
            execute_preprocessor.preprocess(notebook, {'metadata': {'path': 'examples/tutorials/'}})
